"""Attach pd-nodes and merge detected isotherm drafts into a session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.barycentric import corners_from_calibration
from source_extract.review.binary_axes import is_binary_draft
from source_extract.review.retrace import smooth_curve_from_image_waypoints
from source_extract.review.session_common import _as_wt_list


def _read_curves_pixel_origin(system_id: str) -> tuple[float, float]:
    needle = system_id.lower()
    root = RP.dataset_dir() / "configs"
    if root.is_dir():
        for path in root.glob("*.curves.config.json"):
            stem = path.name.replace(".curves.config.json", "")
            if stem.lower() != needle:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                break
            origin = data.get("pixelOrigin")
            if isinstance(origin, (list, tuple)) and len(origin) == 2:
                return float(origin[0]), float(origin[1])
            break
    return 0.0, 0.0


def _ensure_page_calibration(draft: dict[str, Any], pixel_origin: tuple[float, float]) -> None:
    """Lift stored/crop calibration into page pixels (idempotent).

    Binary drafts store ``calibration`` as prose (and ``axes`` as the structured
    map) — never lift those.
    """
    if is_binary_draft(draft):
        return
    dig = draft.setdefault("digitization", {})
    if dig.get("calibrationSpace") == "page":
        return
    cal = dig.get("calibration")
    if not isinstance(cal, dict):
        return
    ox, oy = pixel_origin
    for key, val in list(cal.items()):
        if isinstance(val, (list, tuple)) and len(val) == 2:
            cal[key] = [float(val[0]) + ox, float(val[1]) + oy]
    dig["calibration"] = cal
    dig["calibrationSpace"] = "page"
    dig["storedPixelOrigin"] = [ox, oy]


def _load_nodes_file(system_id: str) -> list[dict[str, Any]]:
    needle = system_id.lower()
    root = RP.work_dir() / "nodes"
    if not root.is_dir():
        return []
    for path in root.glob("*.json"):
        if path.stem.lower() != needle:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []
    return []


def _attach_nodes(session: dict[str, Any], *, force: bool = False) -> None:
    """Load pd-nodes into the session once. Edits (deletes) persist with the session JSON.

    Pass ``force=True`` on create / reload-draft to refresh from the pipeline file.
    """
    if not force and "nodes" in session and session["nodes"] is not None:
        return
    session["nodes"] = _load_nodes_file(session.get("systemId") or "")
    ox, oy = session.get("pixelOrigin") or (0.0, 0.0)
    if isinstance(ox, list):
        ox, oy = float(ox[0]), float(ox[1])
    session["pixelOrigin"] = [float(ox), float(oy)]


def _load_isotherm_draft(system_id: str) -> list[dict[str, Any]]:
    needle = system_id.lower()
    root = RP.work_dir() / "isotherms"
    if not root.is_dir():
        return []
    for path in root.glob("*.json"):
        if path.stem.lower() != needle:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return list(data.get("isotherms") or [])
    return []


def _waypoint_pixels(entry: dict[str, Any]) -> list[list[float]]:
    """Flatten detect-isotherms start/waypoints/end into stored-pixel chain."""
    pts: list[list[float]] = []
    start = entry.get("startPixel")
    if isinstance(start, (list, tuple)) and len(start) >= 2:
        pts.append([float(start[0]), float(start[1])])
    for wp in entry.get("waypoints") or []:
        if isinstance(wp, dict):
            pix = wp.get("pixel")
            if isinstance(pix, (list, tuple)) and len(pix) >= 2:
                pts.append([float(pix[0]), float(pix[1])])
        elif isinstance(wp, (list, tuple)) and len(wp) >= 2:
            pts.append([float(wp[0]), float(wp[1])])
    end = entry.get("endPixel")
    if isinstance(end, (list, tuple)) and len(end) >= 2:
        pts.append([float(end[0]), float(end[1])])
    # dedupe consecutive
    out: list[list[float]] = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 0.5 or abs(p[1] - out[-1][1]) > 0.5:
            out.append(p)
    return out


def merge_detected_isotherms(draft: dict[str, Any], system_id: str, pixel_origin: tuple[float, float]) -> int:
    """Fill empty isotherm polylines from ``isotherms/<system>.json`` (pd-isotherms draft).

    Returns number of isotherms that gained a polyline.
    """
    detected = _load_isotherm_draft(system_id)
    if not detected:
        return 0
    components = list(draft.get("components") or [])
    if len(components) != 3:
        return 0
    _ensure_page_calibration(draft, pixel_origin)
    corners = corners_from_calibration(components, draft["digitization"]["calibration"])
    ox, oy = pixel_origin

    existing = draft.setdefault("isotherms", [])
    # Drop stubs with no geometry so we can replace from detection
    kept = [iso for iso in existing if iso.get("polyline_wt")]
    filled = 0
    for entry in detected:
        stored = _waypoint_pixels(entry)
        if len(stored) < 2:
            continue
        # stored → page, then densify with page corners / origin 0
        page_wps = [[p[0] + ox, p[1] + oy] for p in stored]
        try:
            # page coords as "image" with origin 0 → smooth approximation curve
            control_wt, poly = smooth_curve_from_image_waypoints(
                [(p[0], p[1]) for p in page_wps],
                corners=corners,
                origin=(0.0, 0.0),
                samples_per_segment=18,
            )
        except Exception:
            continue
        if len(poly) < 2:
            continue
        kept.append(
            {
                "field": entry.get("field"),
                "temperature_C": entry.get("temperature_C"),
                "dashed": bool(entry.get("dashed")),
                "control_wt": control_wt,
                "polyline_wt": poly,
                "notes": entry.get("notes"),
            }
        )
        filled += 1
    draft["isotherms"] = kept
    return filled


def _stored_to_image_pixel(
    stored: Sequence[float],
    *,
    pixel_origin: tuple[float, float],
    page_origin: tuple[float, float],
) -> list[float]:
    px = float(stored[0]) + pixel_origin[0] - page_origin[0]
    py = float(stored[1]) + pixel_origin[1] - page_origin[1]
    return [round(px, 2), round(py, 2)]


def _page_to_image_pixel(
    page: Sequence[float],
    *,
    page_origin: tuple[float, float],
) -> list[float]:
    return [round(float(page[0]) - page_origin[0], 2), round(float(page[1]) - page_origin[1], 2)]


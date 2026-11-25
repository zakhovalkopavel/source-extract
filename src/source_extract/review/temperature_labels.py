"""Assign isotherm temperatures from printed diagram labels the curve passes through."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

from source_extract.review import review_paths as RP
from source_extract.review.retrace import polyline_wt_to_image_pixels

# label '1700' (52) at (1292, 1302)  |  label '1400' beside the line at (933, 1136)
_LABEL_AT = re.compile(
    r"label\s+['\"](~?\d{3,4})['\"][^;\n]{0,100}?"
    r"(?:at|beside the line at)\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)
_GAP_AT = re.compile(r"joined across a \d+ px gap at \(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)")
_TEMP_TOKEN = re.compile(r"^~?(\d{3,4})$")
_RANGE_C = (300.0, 3000.0)
# Curve “goes through” the printed number when within this many image pixels of the label centre
THROUGH_LABEL_PX = 36.0


def parse_printed_temperature(text: str) -> float | None:
    """Return °C for a short numeric temperature token, else None."""
    match = _TEMP_TOKEN.match(str(text).strip())
    if match is None:
        return None
    value = float(match.group(1))
    return value if _RANGE_C[0] <= value <= _RANGE_C[1] else None


def labels_from_notes(notes: str | None, *, temperature_C: float | None = None) -> list[tuple[float, float, float]]:
    """Parse ``(temperature_C, stored_x, stored_y)`` from detect-isotherms note text."""
    if not notes:
        return []
    out: list[tuple[float, float, float]] = []
    for match in _LABEL_AT.finditer(notes):
        value = parse_printed_temperature(match.group(1))
        if value is None:
            continue
        out.append((value, float(match.group(2)), float(match.group(3))))
    # Gap joins through a printed numeral: use the known piece temperature at the gap
    if temperature_C is not None and "label gap" in notes.lower():
        for match in _GAP_AT.finditer(notes):
            out.append((float(temperature_C), float(match.group(1)), float(match.group(2))))
    return out


def _load_isotherm_draft_entries(system_id: str) -> list[dict[str, Any]]:
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


def collect_temperature_labels(
    session: dict[str, Any],
) -> list[dict[str, float]]:
    """Printed temperature label centres in **image** pixels for this session."""
    from source_extract.review.nodes_attach import _stored_to_image_pixel  # local import: avoid cycle at module load

    draft = session["draft"]
    origin = tuple(session["image"]["pageOrigin"])
    stored_origin = session.get("pixelOrigin") or draft.get("digitization", {}).get("storedPixelOrigin") or [0, 0]
    cfg_origin = (float(stored_origin[0]), float(stored_origin[1]))

    raw: list[tuple[float, float, float]] = []
    for entry in _load_isotherm_draft_entries(str(session.get("systemId") or "")):
        raw.extend(labels_from_notes(entry.get("notes"), temperature_C=entry.get("temperature_C")))
    for iso in draft.get("isotherms") or []:
        raw.extend(labels_from_notes(iso.get("notes"), temperature_C=iso.get("temperature_C")))

    # Deduplicate near-identical label centres
    labels: list[dict[str, float]] = []
    for value, sx, sy in raw:
        ix, iy = _stored_to_image_pixel(
            [sx, sy], pixel_origin=cfg_origin, page_origin=origin  # type: ignore[arg-type]
        )
        if any(
            abs(ix - L["x"]) < 4 and abs(iy - L["y"]) < 4 and L["temperature_C"] == value for L in labels
        ):
            continue
        labels.append({"temperature_C": float(value), "x": float(ix), "y": float(iy)})
    return labels


def _dist_point_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    len2 = dx * dx + dy * dy
    if len2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def min_distance_to_polyline(
    point: Sequence[float], polyline: Sequence[Sequence[float]]
) -> float:
    if not polyline:
        return float("inf")
    px, py = float(point[0]), float(point[1])
    if len(polyline) == 1:
        return math.hypot(px - float(polyline[0][0]), py - float(polyline[0][1]))
    best = float("inf")
    for i in range(len(polyline) - 1):
        a, b = polyline[i], polyline[i + 1]
        best = min(
            best,
            _dist_point_to_segment(px, py, float(a[0]), float(a[1]), float(b[0]), float(b[1])),
        )
    return best


def temperature_for_polyline(
    polyline_img: Sequence[Sequence[float]],
    labels: Sequence[dict[str, float]],
    *,
    reach_px: float = THROUGH_LABEL_PX,
) -> tuple[float | None, float | None]:
    """Best label temperature the polyline passes through, and its distance.

    If several different temperatures lie within ``reach_px``, the closest wins.
    """
    best_t: float | None = None
    best_d: float | None = None
    for lab in labels:
        d = min_distance_to_polyline((lab["x"], lab["y"]), polyline_img)
        if d > reach_px:
            continue
        if best_d is None or d < best_d - 1e-6:
            best_d = d
            best_t = float(lab["temperature_C"])
        elif best_d is not None and abs(d - best_d) <= 1e-6 and best_t != lab["temperature_C"]:
            # Ambiguous tie between two different labels — leave unset
            return None, d
    return best_t, best_d


def assign_isotherm_temps_from_labels(
    session: dict[str, Any],
    *,
    only_missing: bool = False,
    respect_user: bool = True,
    reach_px: float = THROUGH_LABEL_PX,
) -> int:
    """Set ``temperature_C`` when an isotherm polyline goes through a printed °C label.

    A curve that passes through text such as ``1700`` / ``1500`` takes that value.
    User-saved isotherms (provenance ``user``) are left alone when ``respect_user`` is True.
    Returns the number of isotherms updated. Does not push undo / save — caller owns that.
    """
    from source_extract.review.session_common import _corners_origin

    labels = collect_temperature_labels(session)
    if not labels:
        return 0
    components, corners, origin = _corners_origin(session)
    prov = session.get("provenance", {}).get("isotherms", {})
    assigned = 0
    for i, iso in enumerate(session["draft"].get("isotherms") or []):
        if respect_user and prov.get(str(i)) == "user" and iso.get("temperature_C") is not None:
            continue
        if only_missing and iso.get("temperature_C") is not None:
            continue
        # Prefer dense polyline; fall back to controls
        poly = iso.get("polyline_wt") or iso.get("control_wt") or []
        if len(poly) < 2:
            continue
        pixels = polyline_wt_to_image_pixels(
            poly, corners=corners, origin=origin, components=components
        )
        value, dist = temperature_for_polyline(pixels, labels, reach_px=reach_px)
        if value is None or dist is None:
            continue
        prev = iso.get("temperature_C")
        if prev is not None and float(prev) == float(value):
            continue
        iso["temperature_C"] = float(value)
        note = f"temperature from printed label {value:g} °C (curve within {dist:.0f} px)"
        existing = str(iso.get("notes") or "").strip()
        if "temperature from printed label" not in existing:
            iso["notes"] = f"{existing}; {note}".strip("; ").strip()
        assigned += 1
    return assigned

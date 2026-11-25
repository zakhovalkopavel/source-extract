"""Join two boundaries / isotherms into one polyline at a shared vertex."""

from __future__ import annotations

import math
from typing import Any

from source_extract.review.contour_meta import _reindex_provenance
from source_extract.review.retrace import (
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
)
from source_extract.review.session_common import ContourKind, _corners_origin
from source_extract.review.session_persist import _push_undo, save_session


def _dist(a: list[float], b: list[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _controls_for(
    entry: dict[str, Any],
    *,
    corners: Any,
    origin: Any,
    components: list[str],
) -> tuple[list[list[float]], list[list[float]]]:
    """Return ``(control_wt, control_image_pixels)``."""
    controls = list(entry.get("control_wt") or [])
    if not controls:
        poly = list(entry.get("polyline_wt") or [])
        if poly:
            step = max(1, (len(poly) - 1) // 12)
            controls = [poly[j] for j in range(0, len(poly), step)]
            if controls[-1] != poly[-1]:
                controls.append(poly[-1])
    if len(controls) < 2:
        return controls, []
    img = polyline_wt_to_image_pixels(
        controls, corners=corners, origin=origin, components=components
    )
    return controls, img


def join_contours_at_vertex(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    keep_index: int,
    other_index: int,
    other_point_index: int,
    image_pixel: list[float] | None = None,
) -> dict[str, Any]:
    """Merge ``other`` into ``keep`` at ``other``'s vertex; deletes ``other``.

    The clicked vertex on ``other`` becomes the connection hub: ``keep`` is
    oriented so its nearer end meets that vertex, then the longer branch of
    ``other`` from the vertex is appended. Same-kind only (boundary↔boundary,
    isotherm↔isotherm).
    """
    del image_pixel  # vertex index is authoritative
    if contour_kind not in ("boundary", "isotherm"):
        raise ValueError("Join only supports boundary or isotherm")
    key = "boundaryCurves" if contour_kind == "boundary" else "isotherms"
    prov_key = "boundaries" if contour_kind == "boundary" else "isotherms"
    curves = session["draft"].setdefault(key, [])
    if keep_index < 0 or keep_index >= len(curves):
        raise IndexError(f"{contour_kind} keep index {keep_index} out of range")
    if other_index < 0 or other_index >= len(curves):
        raise IndexError(f"{contour_kind} other index {other_index} out of range")
    if keep_index == other_index:
        raise ValueError("Cannot join a curve to itself")

    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    keep = curves[keep_index]
    other = curves[other_index]
    keep_ctrl, keep_img = _controls_for(
        keep, corners=corners, origin=origin, components=components
    )
    other_ctrl, other_img = _controls_for(
        other, corners=corners, origin=origin, components=components
    )
    if len(keep_ctrl) < 2 or len(other_ctrl) < 2:
        raise ValueError("Both curves need geometry to join")
    if other_point_index < 0 or other_point_index >= len(other_ctrl):
        raise IndexError(f"Point index {other_point_index} out of range on other curve")

    join_wt = [round(float(v), 2) for v in other_ctrl[other_point_index]]
    join_img = other_img[other_point_index]

    # Orient keep so its end is nearer the join vertex
    if keep_img and _dist(keep_img[0], join_img) < _dist(keep_img[-1], join_img):
        keep_ctrl = list(reversed(keep_ctrl))
        keep_img = list(reversed(keep_img))

    # Longer branch of other starting at the join vertex
    branch_fwd = other_ctrl[other_point_index:]
    branch_back = list(reversed(other_ctrl[: other_point_index + 1]))
    branch = branch_fwd if len(branch_fwd) >= len(branch_back) else branch_back
    if len(branch) < 2:
        raise ValueError("Other curve has no branch beyond the join vertex")

    # Avoid duplicating the join vertex
    merged = [list(p) for p in keep_ctrl]
    if _dist(
        polyline_wt_to_image_pixels(
            [merged[-1]], corners=corners, origin=origin, components=components
        )[0],
        join_img,
    ) > 1.5:
        merged.append(join_wt)
    merged.extend([list(p) for p in branch[1:]])

    smooth = rebuild_smooth_from_control_wt(
        merged, corners=corners, origin=origin  # type: ignore[arg-type]
    )
    keep["control_wt"] = merged
    keep["polyline_wt"] = smooth
    keep["notes"] = (keep.get("notes") or "") + "; joined curves"
    if contour_kind == "boundary":
        # Prefer non-empty field labels from either side
        ka = list(keep.get("fields") or [None, None])
        ob = list(other.get("fields") or [None, None])
        while len(ka) < 2:
            ka.append(None)
        while len(ob) < 2:
            ob.append(None)
        keep["fields"] = [ka[0] or ob[0], ka[1] or ob[1]]
        if not keep.get("arrows"):
            keep["arrows"] = other.get("arrows") or ["?"]
    else:
        if keep.get("temperature_C") is None and other.get("temperature_C") is not None:
            keep["temperature_C"] = other.get("temperature_C")
        if not keep.get("field") and other.get("field"):
            keep["field"] = other.get("field")

    del curves[other_index]
    session["provenance"][prov_key] = _reindex_provenance(
        session["provenance"].get(prov_key, {}), other_index
    )
    # keep_index may have shifted if other_index < keep_index
    new_keep = keep_index - 1 if other_index < keep_index else keep_index
    session["provenance"].setdefault(prov_key, {})[str(new_keep)] = "user"
    if other_index < keep_index:
        # provenance reindex already shifted keys > other
        pass
    session["_lastContourJoin"] = {
        "kind": contour_kind,
        "index": new_keep,
        "removed": other_index,
        "pointIndex": other_point_index,
    }
    save_session(session)
    return session

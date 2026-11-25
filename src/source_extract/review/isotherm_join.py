"""Join same-temperature isotherm pieces into one curve or closed circuit."""

from __future__ import annotations

import math
from typing import Any

from source_extract.review.isotherm_join_helpers import (
    CIRCUIT_CLOSE_PX,
    JOIN_GAP_PX,
    _controls_image,
    _temps_equal,
    chain_control_pieces,
    pieces_interact,
)
from source_extract.review.retrace import (
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
    smooth_curve_from_image_waypoints,
)

def join_same_temperature_isotherms(
    session: dict[str, Any],
    *,
    anchor_index: int,
) -> dict[str, Any]:
    """Merge same-°C isotherms that meet/cross the anchor into one curve/circuit.

    Mutates ``session["draft"]["isotherms"]``. Does not push undo / save.
    Returns a summary for ``_lastIsothermJoin``.
    """
    from source_extract.review.session_common import _corners_origin
    from source_extract.review.contour_point_helpers import _rekey_provenance

    isos = session["draft"].get("isotherms") or []
    if anchor_index < 0 or anchor_index >= len(isos):
        return {"joined": False, "reason": "bad-index"}
    anchor = isos[anchor_index]
    t = anchor.get("temperature_C")
    try:
        if t is None or t == "" or not math.isfinite(float(t)):
            return {"joined": False, "reason": "anchor-no-temperature"}
    except (TypeError, ValueError):
        return {"joined": False, "reason": "anchor-no-temperature"}

    components, corners, origin = _corners_origin(session)
    polys_img: list[list[list[float]]] = []
    ctrls_img: list[list[list[float]]] = []
    for iso in isos:
        poly = iso.get("polyline_wt") or iso.get("control_wt") or []
        if len(poly) < 2:
            polys_img.append([])
            ctrls_img.append([])
            continue
        pix = polyline_wt_to_image_pixels(
            poly, corners=corners, origin=origin, components=components
        )
        polys_img.append(pix)
        ctrls_img.append(
            _controls_image(iso, corners=corners, origin=origin, components=components)
        )

    if len(polys_img[anchor_index]) < 2:
        return {"joined": False, "reason": "anchor-no-geometry"}

    # Connected component of same-temp pieces interacting with the anchor
    member = {anchor_index}
    changed = True
    while changed:
        changed = False
        for i, iso in enumerate(isos):
            if i in member or len(polys_img[i]) < 2:
                continue
            if not _temps_equal(anchor, iso):
                continue
            if any(pieces_interact(polys_img[i], polys_img[j]) for j in member):
                member.add(i)
                changed = True

    if len(member) < 2:
        return {
            "joined": False,
            "reason": "no-neighbours",
            "anchorIndex": anchor_index,
        }

    members = sorted(member)
    pieces = [ctrls_img[i] if len(ctrls_img[i]) >= 2 else polys_img[i] for i in members]
    path_img, closed = chain_control_pieces(pieces)
    if len(path_img) < 2:
        return {"joined": False, "reason": "empty-path", "anchorIndex": anchor_index}

    # Drop duplicate closing vertex before wt conversion if present (keep closed flag)
    build_pts = path_img
    if closed and len(build_pts) >= 2 and _dist(build_pts[0], build_pts[-1]) <= 1.5:
        build_pts = build_pts[:-1]

    control_wt, poly_wt = smooth_curve_from_image_waypoints(
        [(p[0], p[1]) for p in build_pts],
        corners=corners,  # type: ignore[arg-type]
        origin=origin,  # type: ignore[arg-type]
        reorder_nearest=False,
    )
    if closed and control_wt and control_wt[0] != control_wt[-1]:
        # Close dense polyline: rebuild with repeated first control
        control_closed = list(control_wt) + [list(control_wt[0])]
        poly_wt = rebuild_smooth_from_control_wt(
            control_closed, corners=corners, origin=origin  # type: ignore[arg-type]
        )
        control_wt = control_closed

    # Keep the lowest index as the survivor; delete the rest
    keep = members[0]
    merged_from = [i for i in members if i != keep]
    survivor = isos[keep]
    survivor["control_wt"] = control_wt
    survivor["polyline_wt"] = poly_wt
    survivor["closed"] = bool(closed)
    note = (
        f"joined {len(members)} same-temperature pieces"
        + (" into closed circuit" if closed else " into one curve")
    )
    existing = str(survivor.get("notes") or "").strip()
    if "joined" not in existing.lower():
        survivor["notes"] = f"{existing}; {note}".strip("; ").strip()
    # Prefer non-empty field from any member
    if not survivor.get("field"):
        for i in members:
            f = (isos[i].get("field") or "").strip()
            if f:
                survivor["field"] = f
                break

    for i in sorted(merged_from, reverse=True):
        del isos[i]
        session["provenance"]["isotherms"].pop(str(i), None)
        _rekey_provenance(session["provenance"]["isotherms"], removed=i)
        if keep > i:
            keep -= 1

    session["provenance"].setdefault("isotherms", {})[str(keep)] = "user"
    summary = {
        "joined": True,
        "index": keep,
        "mergedCount": len(merged_from),
        "mergedFrom": merged_from,
        "closed": closed,
        "controlCount": len(control_wt),
        "temperature_C": survivor.get("temperature_C"),
    }
    session["_lastIsothermJoin"] = summary
    return summary


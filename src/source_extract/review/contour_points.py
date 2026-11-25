"""Public contour vertex move / add / delete operations."""

from __future__ import annotations

import math
from typing import Any, Sequence

from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt
from source_extract.review.contour_point_helpers import (
    _delete_point_no_undo,
    _mover_identity,
    _nearest_segment_index,
    _rekey_provenance,
)
from source_extract.review.retrace import (
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
)
from source_extract.review.session_common import ContourKind, _corners_origin
from source_extract.review.session_persist import _push_undo, save_session


def move_point(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    contour_index: int,
    point_index: int,
    image_pixel: list[float],
) -> dict[str, Any]:
    """Move a curve control. Shared co-located points move with it; no reorder."""
    _push_undo(session)
    from source_extract.review.isotherm_boundary_snap import (
        IMAGE_POINT_TOL_PX,
        snap_image_to_existing_landmark,
        snap_image_to_nearest_boundary,
    )
    from source_extract.review.point_topology import (
        _pixel_of_mover,
        finish_topology_move,
    )

    mover = _mover_identity(
        type="vertex", kind=contour_kind, index=contour_index, point_index=point_index
    )
    old_pixel = _pixel_of_mover(session, mover)

    pixel = list(image_pixel)
    landmark = snap_image_to_existing_landmark(
        session,
        pixel,
        radius_px=IMAGE_POINT_TOL_PX,
        exclude_contour=(contour_kind, contour_index),
    )
    if landmark is not None:
        pixel = landmark
    elif contour_kind == "isotherm":
        iso_preview = session["draft"]["isotherms"][contour_index]
        n_ctrl = len(iso_preview.get("control_wt") or iso_preview.get("polyline_wt") or [])
        if point_index == 0 or point_index == n_ctrl - 1:
            snapped = snap_image_to_nearest_boundary(session, pixel)
            if snapped is not None:
                pixel = snapped

    session["_lastMoveNote"] = finish_topology_move(
        session, mover=mover, old_pixel=old_pixel, new_pixel=pixel
    )
    save_session(session)
    return session


def delete_point(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    contour_index: int,
    point_index: int,
) -> dict[str, Any]:
    _push_undo(session)
    _delete_point_no_undo(
        session,
        contour_kind=contour_kind,
        contour_index=contour_index,
        point_index=point_index,
    )
    save_session(session)
    return session


def delete_points_batch(
    session: dict[str, Any],
    *,
    items: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Delete many invariants / pd-nodes / contour controls in one undo step.

    ``items`` entries:
      - ``{"type": "invariant", "id": "..."}``
      - ``{"type": "node", "index": i}``  (pd-nodes index)
      - ``{"type": "vertex", "kind": "boundary"|"isotherm", "index": i, "pointIndex": j}``
    """
    _push_undo(session)
    inv_ids = {it["id"] for it in items if it.get("type") == "invariant" and it.get("id")}
    if inv_ids:
        session["draft"]["invariantPoints"] = [
            p for p in session["draft"]["invariantPoints"] if p["id"] not in inv_ids
        ]
        for iid in inv_ids:
            session.get("provenance", {}).get("points", {}).pop(iid, None)

    node_idxs = sorted(
        {int(it["index"]) for it in items if it.get("type") == "node" and it.get("index") is not None},
        reverse=True,
    )
    if node_idxs:
        nodes = list(session.get("nodes") or [])
        for ni in node_idxs:
            if 0 <= ni < len(nodes):
                del nodes[ni]
        session["nodes"] = nodes

    by_contour: dict[tuple[str, int], list[int]] = {}
    for it in items:
        if it.get("type") != "vertex":
            continue
        kind = it.get("kind")
        idx = it.get("index")
        pi = it.get("pointIndex")
        if kind not in ("boundary", "isotherm") or idx is None or pi is None:
            continue
        by_contour.setdefault((str(kind), int(idx)), []).append(int(pi))

    for (kind, cidx) in sorted(by_contour.keys(), key=lambda k: k[1], reverse=True):
        indices = sorted(set(by_contour[(kind, cidx)]), reverse=True)
        if kind == "isotherm":
            isos = session["draft"]["isotherms"]
            if cidx < 0 or cidx >= len(isos):
                continue
            controls = list(isos[cidx].get("control_wt") or isos[cidx].get("polyline_wt") or [])
            if len(controls) - len(indices) < 2:
                del isos[cidx]
                session["provenance"]["isotherms"].pop(str(cidx), None)
                _rekey_provenance(session["provenance"]["isotherms"], removed=cidx)
                continue
            for pi in indices:
                if 0 <= pi < len(controls):
                    del controls[pi]
            _, corners, origin = _corners_origin(session)
            isos[cidx]["control_wt"] = controls
            isos[cidx]["polyline_wt"] = rebuild_smooth_from_control_wt(
                controls, corners=corners, origin=origin  # type: ignore[arg-type]
            )
            session["provenance"]["isotherms"][str(cidx)] = "user"
            from source_extract.review.isotherm_boundary_snap import (
                snap_isotherm_ends_to_boundaries,
            )

            snap_isotherm_ends_to_boundaries(session, contour_index=cidx)
        else:
            bcs = session["draft"]["boundaryCurves"]
            if cidx < 0 or cidx >= len(bcs):
                continue
            poly = bcs[cidx]["polyline_wt"]
            if len(poly) - len(indices) < 2:
                del bcs[cidx]
                session["provenance"]["boundaries"].pop(str(cidx), None)
                _rekey_provenance(session["provenance"]["boundaries"], removed=cidx)
                continue
            for pi in indices:
                if 0 <= pi < len(poly):
                    del poly[pi]
            session["provenance"]["boundaries"][str(cidx)] = "user"

    save_session(session)
    return session


def add_point(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    contour_index: int,
    image_pixel: list[float],
    after_index: int | None = None,
) -> dict[str, Any]:
    """Insert a point on a contour between the nearest segment endpoints when close.

    If a landmark already exists within image-pixel tolerance, reuse it (no insert).
    Near a curve: insert between the two points of the closest segment.
    Otherwise: same nearest-segment insert (existing algorithm).
    """
    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    from source_extract.review.isotherm_boundary_snap import (
        IMAGE_POINT_TOL_PX,
        snap_image_to_existing_landmark,
        snap_image_to_nearest_boundary,
        snap_isotherm_ends_to_boundaries,
    )
    from source_extract.review.point_topology import join_nearby_curves

    pixel = list(image_pixel)
    landmark = snap_image_to_existing_landmark(
        session,
        pixel,
        radius_px=IMAGE_POINT_TOL_PX,
        exclude_contour=(contour_kind, contour_index),
    )
    if landmark is not None:
        pixel = landmark

    page = image_to_page_pixel((pixel[0], pixel[1]), origin)  # type: ignore[arg-type]
    wt = list(page_pixel_to_wt(page, corners))

    if contour_kind == "boundary":
        bc = session["draft"]["boundaryCurves"][contour_index]
        controls = list(bc.get("control_wt") or [])
        if not controls:
            poly = list(bc.get("polyline_wt") or [])
            if poly:
                step = max(1, (len(poly) - 1) // 12)
                controls = [poly[j] for j in range(0, len(poly), step)]
                if controls[-1] != poly[-1]:
                    controls.append(poly[-1])
        ctrl_img = polyline_wt_to_image_pixels(
            controls, corners=corners, origin=origin, components=components
        )
        for j, p in enumerate(ctrl_img):
            if math.hypot(float(p[0]) - pixel[0], float(p[1]) - pixel[1]) <= IMAGE_POINT_TOL_PX:
                session["_lastAddNote"] = f"Reused existing boundary control #{j}"
                save_session(session)
                return session
        if after_index is None:
            after_index = _nearest_segment_index(pixel, ctrl_img)
        # Insert between the two closest segment endpoints when near the curve.
        insert_at = after_index + 1
        controls.insert(insert_at, [round(float(v), 2) for v in wt])
        bc["control_wt"] = controls
        bc["polyline_wt"] = rebuild_smooth_from_control_wt(
            controls, corners=corners, origin=origin  # type: ignore[arg-type]
        )
        session["provenance"]["boundaries"][str(contour_index)] = "user"
        join_nearby_curves(session, pixel)
    else:
        iso = session["draft"]["isotherms"][contour_index]
        controls = list(iso.get("control_wt") or iso.get("polyline_wt") or [])
        ctrl_img = polyline_wt_to_image_pixels(
            controls, corners=corners, origin=origin, components=components
        )
        for j, p in enumerate(ctrl_img):
            if math.hypot(float(p[0]) - pixel[0], float(p[1]) - pixel[1]) <= IMAGE_POINT_TOL_PX:
                session["_lastAddNote"] = f"Reused existing isotherm control #{j}"
                save_session(session)
                return session
        if after_index is None:
            after_index = _nearest_segment_index(pixel, ctrl_img)
        insert_at = after_index + 1
        if insert_at == 0 or insert_at == len(controls):
            snapped = snap_image_to_nearest_boundary(session, pixel)
            if snapped is not None:
                pixel = snapped
                page = image_to_page_pixel((pixel[0], pixel[1]), origin)  # type: ignore[arg-type]
                wt = list(page_pixel_to_wt(page, corners))
        controls.insert(insert_at, [round(float(v), 2) for v in wt])
        iso["control_wt"] = controls
        iso["polyline_wt"] = rebuild_smooth_from_control_wt(
            controls, corners=corners, origin=origin  # type: ignore[arg-type]
        )
        session["provenance"]["isotherms"][str(contour_index)] = "user"
        snap_isotherm_ends_to_boundaries(session, contour_index=contour_index)
        join_nearby_curves(session, pixel)
    save_session(session)
    return session

"""Internal helpers for contour point edits and overlap coalesce."""

from __future__ import annotations

from typing import Any, Sequence

from source_extract.review.nodes_attach import _stored_to_image_pixel
from source_extract.review.retrace import polyline_wt_to_image_pixels, rebuild_smooth_from_control_wt
from source_extract.review.session_common import ContourKind, _corners_origin

# Image-pixel radius — matches frontend IMAGE_POINT_TOL_PX (screen ≈ this × scale).
POINT_COALESCE_RADIUS_PX = 4.0


def _boundary_handle_indices(pixel_count: int) -> list[int]:
    if pixel_count <= 0:
        return []
    if pixel_count <= 14:
        return list(range(pixel_count))
    idxs = {0, pixel_count - 1}
    step = max(1, (pixel_count - 1) // 12)
    for i in range(step, pixel_count - 1, step):
        idxs.add(i)
    return sorted(idxs)


def _mover_identity(
    *,
    type: str,
    id: str | None = None,
    index: int | None = None,
    kind: str | None = None,
    point_index: int | None = None,
) -> dict[str, Any]:
    return {
        "type": type,
        "id": id,
        "index": index,
        "kind": kind,
        "pointIndex": point_index,
    }


def _is_same_point(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("type") != b.get("type"):
        return False
    if a["type"] == "invariant":
        return a.get("id") is not None and a.get("id") == b.get("id")
    if a["type"] == "node":
        return a.get("index") is not None and int(a["index"]) == int(b["index"])
    return (
        a.get("kind") == b.get("kind")
        and a.get("index") is not None
        and b.get("index") is not None
        and int(a["index"]) == int(b["index"])
        and a.get("pointIndex") is not None
        and b.get("pointIndex") is not None
        and int(a["pointIndex"]) == int(b["pointIndex"])
    )


def _list_discrete_landmarks(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Sparse editable landmarks (not dense boundary polyline samples).

    Includes invariants, nodes, isotherm controls, boundary control handles,
    and calibration triangle corners. Shared vertices across curves are OK —
    coalesce / snap reuse these instead of inventing near-duplicates.
    """
    components, corners, origin = _corners_origin(session)
    draft = session["draft"]
    stored_origin = session.get("pixelOrigin") or draft.get("digitization", {}).get(
        "storedPixelOrigin"
    ) or [0, 0]
    cfg_origin = (float(stored_origin[0]), float(stored_origin[1]))
    out: list[dict[str, Any]] = []

    # Triangle frame corners (diagram vertices)
    for i, name in enumerate(components):
        pure = [100.0 if j == i else 0.0 for j in range(len(components))]
        pix = polyline_wt_to_image_pixels(
            [pure], corners=corners, origin=origin, components=components
        )[0]
        out.append(
            {
                "type": "frame",
                "index": i,
                "id": name,
                "x": float(pix[0]),
                "y": float(pix[1]),
            }
        )

    for inv in draft.get("invariantPoints", []):
        wt = [inv["liquid_wt"][c] for c in components]
        pix = polyline_wt_to_image_pixels(
            [wt], corners=corners, origin=origin, components=components
        )[0]
        out.append(
            {"type": "invariant", "id": inv["id"], "x": float(pix[0]), "y": float(pix[1])}
        )

    for node_index, node in enumerate(session.get("nodes") or []):
        stored = node.get("pixel") or [0, 0]
        wt = node.get("wt")
        if isinstance(wt, (list, tuple)) and len(wt) == len(components):
            try:
                pix = polyline_wt_to_image_pixels(
                    [list(wt)], corners=corners, origin=origin, components=components
                )[0]
            except Exception:  # noqa: BLE001
                pix = _stored_to_image_pixel(
                    stored, pixel_origin=cfg_origin, page_origin=origin  # type: ignore[arg-type]
                )
        else:
            pix = _stored_to_image_pixel(
                stored, pixel_origin=cfg_origin, page_origin=origin  # type: ignore[arg-type]
            )
        out.append(
            {
                "type": "node",
                "index": node_index,
                "id": node.get("label") or node.get("id"),
                "kind": node.get("kind"),
                "x": float(pix[0]),
                "y": float(pix[1]),
            }
        )

    for i, bc in enumerate(draft.get("boundaryCurves", [])):
        controls = list(bc.get("control_wt") or [])
        if controls:
            pixels = polyline_wt_to_image_pixels(
                controls, corners=corners, origin=origin, components=components
            )
            for j, pix in enumerate(pixels):
                out.append(
                    {
                        "type": "vertex",
                        "kind": "boundary",
                        "index": i,
                        "pointIndex": j,
                        "x": float(pix[0]),
                        "y": float(pix[1]),
                    }
                )
        else:
            poly = bc.get("polyline_wt") or []
            pixels = polyline_wt_to_image_pixels(
                poly, corners=corners, origin=origin, components=components
            )
            for j in _boundary_handle_indices(len(pixels)):
                pix = pixels[j]
                out.append(
                    {
                        "type": "vertex",
                        "kind": "boundary",
                        "index": i,
                        "pointIndex": j,
                        "x": float(pix[0]),
                        "y": float(pix[1]),
                    }
                )

    for i, iso in enumerate(draft.get("isotherms", [])):
        controls = iso.get("control_wt") or []
        if controls:
            pixels = polyline_wt_to_image_pixels(
                controls, corners=corners, origin=origin, components=components
            )
            for j, pix in enumerate(pixels):
                out.append(
                    {
                        "type": "vertex",
                        "kind": "isotherm",
                        "index": i,
                        "pointIndex": j,
                        "x": float(pix[0]),
                        "y": float(pix[1]),
                    }
                )
        else:
            poly = iso.get("polyline_wt") or []
            pixels = polyline_wt_to_image_pixels(
                poly, corners=corners, origin=origin, components=components
            )
            for j in _boundary_handle_indices(len(pixels)):
                pix = pixels[j]
                out.append(
                    {
                        "type": "vertex",
                        "kind": "isotherm",
                        "index": i,
                        "pointIndex": j,
                        "x": float(pix[0]),
                        "y": float(pix[1]),
                    }
                )
    return out


def _list_point_locations(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Alias — coalesce / snap use discrete landmarks only."""
    return _list_discrete_landmarks(session)


def _overlaps_at(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    exclude: dict[str, Any],
    radius_px: float = POINT_COALESCE_RADIUS_PX,
) -> list[dict[str, Any]]:
    x, y = float(image_pixel[0]), float(image_pixel[1])
    r2 = radius_px * radius_px
    hits: list[dict[str, Any]] = []
    for loc in _list_discrete_landmarks(session):
        if loc.get("type") == "frame":
            # Frame corners are never deleted by coalesce — they are shared anchors.
            continue
        if _is_same_point(exclude, loc):
            continue
        dx = float(loc["x"]) - x
        dy = float(loc["y"]) - y
        if dx * dx + dy * dy <= r2:
            hits.append(loc)
    return hits


def _delete_invariant_no_undo(session: dict[str, Any], point_id: str) -> None:
    session["draft"]["invariantPoints"] = [
        p for p in session["draft"]["invariantPoints"] if p["id"] != point_id
    ]
    session["provenance"]["points"].pop(point_id, None)


def _delete_node_no_undo(session: dict[str, Any], node_index: int) -> None:
    nodes = list(session.get("nodes") or [])
    if 0 <= node_index < len(nodes):
        del nodes[node_index]
        session["nodes"] = nodes


def _delete_mover_no_undo(session: dict[str, Any], mover: dict[str, Any]) -> None:
    if mover["type"] == "invariant":
        _delete_invariant_no_undo(session, str(mover["id"]))
    elif mover["type"] == "node":
        _delete_node_no_undo(session, int(mover["index"]))
    else:
        _delete_point_no_undo(
            session,
            contour_kind=mover["kind"],  # type: ignore[arg-type]
            contour_index=int(mover["index"]),
            point_index=int(mover["pointIndex"]),
        )


def _delete_overlap_targets_no_undo(session: dict[str, Any], targets: Sequence[dict[str, Any]]) -> int:
    """Delete coincident non-invariant targets; high indices first so lists stay valid."""
    removed = 0
    vertices = sorted(
        [t for t in targets if t.get("type") == "vertex"],
        key=lambda t: (int(t["index"]), int(t["pointIndex"])),
        reverse=True,
    )
    for t in vertices:
        _delete_point_no_undo(
            session,
            contour_kind=t["kind"],  # type: ignore[arg-type]
            contour_index=int(t["index"]),
            point_index=int(t["pointIndex"]),
        )
        removed += 1
    nodes = sorted(
        [t for t in targets if t.get("type") == "node"],
        key=lambda t: int(t["index"]),
        reverse=True,
    )
    for t in nodes:
        _delete_node_no_undo(session, int(t["index"]))
        removed += 1
    return removed


def _finish_move_coalesce(
    session: dict[str, Any],
    *,
    mover: dict[str, Any],
    image_pixel: list[float],
) -> str | None:
    """Delegate to topology (priority replace + shared cluster + curve join)."""
    from source_extract.review.point_topology import finish_topology_move

    return finish_topology_move(
        session, mover=mover, old_pixel=None, new_pixel=image_pixel
    )


def _rekey_provenance(prov: dict[str, Any], *, removed: int) -> None:
    """After deleting contour ``removed``, shift higher string keys down by 1."""
    updated: dict[str, Any] = {}
    for k, v in list(prov.items()):
        try:
            i = int(k)
        except (TypeError, ValueError):
            updated[k] = v
            continue
        if i < removed:
            updated[k] = v
        elif i > removed:
            updated[str(i - 1)] = v
        # i == removed dropped
    prov.clear()
    prov.update(updated)


def _nearest_segment_index(
    image_pixel: list[float],
    polyline_img: Sequence[Sequence[float]],
) -> int:
    """Index of the segment (i → i+1) closest to the click; used as insert-after."""
    if len(polyline_img) < 2:
        return max(0, len(polyline_img) - 1)
    px, py = float(image_pixel[0]), float(image_pixel[1])
    best_i, best_d = 0, float("inf")
    for i in range(len(polyline_img) - 1):
        ax, ay = float(polyline_img[i][0]), float(polyline_img[i][1])
        bx, by = float(polyline_img[i + 1][0]), float(polyline_img[i + 1][1])
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy or 1.0
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
        qx, qy = ax + t * dx, ay + t * dy
        d = (px - qx) ** 2 + (py - qy) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _delete_point_no_undo(
    session: dict[str, Any],
    *,
    contour_kind: ContourKind,
    contour_index: int,
    point_index: int,
) -> None:
    if contour_kind == "boundary":
        bcs = session["draft"]["boundaryCurves"]
        poly = bcs[contour_index]["polyline_wt"]
        if len(poly) <= 2:
            # last two points → remove the whole boundary
            del bcs[contour_index]
            session["provenance"]["boundaries"].pop(str(contour_index), None)
            _rekey_provenance(session["provenance"]["boundaries"], removed=contour_index)
            return
        del poly[point_index]
        session["provenance"]["boundaries"][str(contour_index)] = "user"
        return
    isos = session["draft"]["isotherms"]
    iso = isos[contour_index]
    controls = list(iso.get("control_wt") or iso.get("polyline_wt") or [])
    if len(controls) <= 2:
        del isos[contour_index]
        session["provenance"]["isotherms"].pop(str(contour_index), None)
        _rekey_provenance(session["provenance"]["isotherms"], removed=contour_index)
        return
    _, corners, origin = _corners_origin(session)
    del controls[point_index]
    iso["control_wt"] = controls
    iso["polyline_wt"] = rebuild_smooth_from_control_wt(controls, corners=corners, origin=origin)  # type: ignore[arg-type]
    session["provenance"]["isotherms"][str(contour_index)] = "user"


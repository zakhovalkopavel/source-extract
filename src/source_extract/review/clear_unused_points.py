"""Remove unused nodes / draft invariants before diagram confirm."""

from __future__ import annotations

import math
from typing import Any

from source_extract.review.isotherm_boundary_snap import (
    IMAGE_POINT_TOL_PX,
    _project_onto_polyline,
)
from source_extract.review.nodes_attach import _stored_to_image_pixel
from source_extract.review.retrace import polyline_wt_to_image_pixels
from source_extract.review.session_common import _corners_origin
from source_extract.review.session_persist import _push_undo, save_session

# Slightly looser than snap — "on a curve" for cleanup.
ON_CURVE_TOL_PX = IMAGE_POINT_TOL_PX * 2.0

# Topology anchors that must never be cleared.
_DIAGRAM_VERTEX_KINDS = frozenset({"corner"})


def _node_image_pixel(
    session: dict[str, Any],
    node: dict[str, Any],
    *,
    components: list[str],
    corners: Any,
    origin: Any,
    cfg_origin: tuple[float, float],
) -> list[float]:
    stored = node.get("pixel") or [0, 0]
    wt = node.get("wt")
    if isinstance(wt, (list, tuple)) and len(wt) == len(components):
        try:
            return list(
                polyline_wt_to_image_pixels(
                    [list(wt)], corners=corners, origin=origin, components=components
                )[0]
            )
        except Exception:  # noqa: BLE001
            pass
    return list(
        _stored_to_image_pixel(
            stored, pixel_origin=cfg_origin, page_origin=origin  # type: ignore[arg-type]
        )
    )


def _contour_polylines_img(session: dict[str, Any]) -> list[list[list[float]]]:
    components, corners, origin = _corners_origin(session)
    out: list[list[list[float]]] = []
    for bc in session["draft"].get("boundaryCurves") or []:
        poly = bc.get("polyline_wt") or []
        if len(poly) < 2:
            continue
        out.append(
            polyline_wt_to_image_pixels(
                poly, corners=corners, origin=origin, components=components
            )
        )
    for iso in session["draft"].get("isotherms") or []:
        controls = iso.get("control_wt") or []
        poly = controls if len(controls) >= 2 else (iso.get("polyline_wt") or [])
        if len(poly) < 2:
            continue
        out.append(
            polyline_wt_to_image_pixels(
                poly, corners=corners, origin=origin, components=components
            )
        )
    return out


def _on_any_curve(image_pixel: list[float], polylines: list[list[list[float]]]) -> bool:
    for poly in polylines:
        hit = _project_onto_polyline(image_pixel, poly)
        if hit is not None and hit[1] <= ON_CURVE_TOL_PX:
            return True
    return False


def _is_special_composition(inv: dict[str, Any]) -> bool:
    if inv.get("pointRole") == "compound":
        return True
    from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag

    enrich = enrich_invariant_from_tag(str(inv.get("id") or ""))
    if enrich.get("resolved"):
        return True
    # Named formula / compound id on the point itself
    for key in ("compoundId", "notation", "label"):
        val = inv.get(key)
        if isinstance(val, str) and val.strip() and not val.lower().startswith("cas-"):
            return True
    return False


def _has_melting_point(inv: dict[str, Any]) -> bool:
    t = inv.get("temperature_C")
    if t is None:
        t = inv.get("temperatureC")
    try:
        return t is not None and math.isfinite(float(t))
    except (TypeError, ValueError):
        return False


def clear_unused_points(session: dict[str, Any]) -> dict[str, Any]:
    """Drop nodes/invariants that carry no diagram meaning.

    Keep a point when **any** of these hold:
    - special composition (compound / compounds.json match)
    - has a melting point (°C)
    - lies on a boundary or isotherm (within ``ON_CURVE_TOL_PX``)
    - is a diagram vertex (calibration ``corner``)
    """
    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    draft = session["draft"]
    stored_origin = session.get("pixelOrigin") or draft.get("digitization", {}).get(
        "storedPixelOrigin"
    ) or [0, 0]
    cfg_origin = (float(stored_origin[0]), float(stored_origin[1]))
    polylines = _contour_polylines_img(session)

    invs = list(draft.get("invariantPoints") or [])
    keep_inv_ids: set[str] = set()
    removed_inv = 0
    kept_invs: list[dict[str, Any]] = []
    for inv in invs:
        iid = str(inv.get("id") or "")
        wt = [inv["liquid_wt"][c] for c in components] if inv.get("liquid_wt") else None
        pix: list[float] | None = None
        if wt is not None:
            try:
                pix = list(
                    polyline_wt_to_image_pixels(
                        [wt], corners=corners, origin=origin, components=components
                    )[0]
                )
            except Exception:  # noqa: BLE001
                pix = None
        keep = (
            _is_special_composition(inv)
            or _has_melting_point(inv)
            or (pix is not None and _on_any_curve(pix, polylines))
        )
        if keep:
            kept_invs.append(inv)
            if iid:
                keep_inv_ids.add(iid)
        else:
            removed_inv += 1
            session.get("provenance", {}).get("points", {}).pop(iid, None)
    draft["invariantPoints"] = kept_invs

    nodes = list(session.get("nodes") or [])
    kept_nodes: list[dict[str, Any]] = []
    removed_nodes = 0
    for node in nodes:
        kind = str(node.get("kind") or "")
        linked = node.get("invariant")
        pix = _node_image_pixel(
            session,
            node,
            components=components,
            corners=corners,
            origin=origin,
            cfg_origin=cfg_origin,
        )
        on_curve = _on_any_curve(pix, polylines)
        special = False
        melting = False
        if linked and isinstance(linked, str):
            if linked in keep_inv_ids:
                special = True
            else:
                # Linked inv may have been kept for other reasons already filtered;
                # also check enrich on the link id.
                from source_extract.review.invariant_compound_lookup import (
                    enrich_invariant_from_tag,
                )

                enrich = enrich_invariant_from_tag(linked)
                special = bool(enrich.get("resolved"))
        if kind == "ring":
            from source_extract.review.invariant_compound_lookup import (
                enrich_invariant_from_tag,
            )

            tag = str(linked or node.get("label") or "")
            enrich = enrich_invariant_from_tag(tag)
            special = special or bool(enrich.get("resolved"))
            if enrich.get("temperature_C") is not None:
                melting = True

        keep = (
            kind in _DIAGRAM_VERTEX_KINDS
            or special
            or melting
            or on_curve
            or (isinstance(linked, str) and linked in keep_inv_ids)
        )
        # Bare invariant-kind nodes that sit on a curve stay; off-curve orphans go.
        if keep:
            kept_nodes.append(node)
        else:
            removed_nodes += 1
    session["nodes"] = kept_nodes

    session["_lastClearUnused"] = {
        "removedNodes": removed_nodes,
        "removedInvariants": removed_inv,
        "keptNodes": len(kept_nodes),
        "keptInvariants": len(kept_invs),
    }
    save_session(session)
    return session

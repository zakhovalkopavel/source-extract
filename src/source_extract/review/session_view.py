"""Build pixel view payloads for boundaries / isotherms / invariants / liquidus."""

from __future__ import annotations

from typing import Any

from source_extract.review.barycentric import corners_from_calibration, normalize_wt
from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft, liquidus_x_wt
from source_extract.review.retrace import (
    control_wt_to_smooth_image_pixels,
    heal_control_wt_order,
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
)
from source_extract.review.session_common import _as_wt_list
from source_extract.review.nodes_attach import _page_to_image_pixel, _stored_to_image_pixel


def _build_binary_view(session: dict[str, Any]) -> dict[str, Any]:
    """Pixel-space view for binary T–x drafts (liquidus + invariants)."""
    draft = session["draft"]
    components = list(draft["components"])
    origin = tuple(session["image"]["pageOrigin"])  # type: ignore[arg-type]
    axes = axes_from_digitization(draft)
    if axes is None:
        raise ValueError(
            f"{session.get('systemId')}: binary draft has no digitization.axes "
            "(and calibration text could not be parsed) — run Analyze / pd-extract"
        )

    points = []
    for inv in draft.get("invariantPoints", []):
        src = (inv.get("sources") or [{}])[0]
        page = src.get("pixel")
        if isinstance(page, (list, tuple)) and len(page) == 2:
            pix = _page_to_image_pixel(page, page_origin=origin)  # type: ignore[arg-type]
        else:
            x_wt = float(inv.get("liquid_wt", {}).get(axes.x_component, 0.0))
            t = float(inv.get("temperature_C") or 0.0)
            page_xy = axes.to_pixel(x_wt, t)
            pix = _page_to_image_pixel(page_xy, page_origin=origin)  # type: ignore[arg-type]
        wt = [float(inv.get("liquid_wt", {}).get(c, 0.0)) for c in components]
        points.append(
            {
                "id": inv["id"],
                "kind": "invariant",
                "temperature_C": inv.get("temperature_C"),
                "composition": {c: inv.get("liquid_wt", {}).get(c) for c in components},
                "wt": wt,
                "pixel": pix,
                "pagePixel": page if isinstance(page, list) else list(page) if page else None,
                "provenance": session["provenance"].get("points", {}).get(inv["id"], "auto"),
            }
        )

    liquidus = []
    for i, branch in enumerate(draft.get("liquidus") or []):
        pts = branch.get("points") or []
        pixels = []
        for pt in pts:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            page_xy = axes.to_pixel(float(pt[0]), float(pt[1]))
            pixels.append(_page_to_image_pixel(page_xy, page_origin=origin))  # type: ignore[arg-type]
        liquidus.append(
            {
                "id": f"liquidus-{i}",
                "index": i,
                "phase": branch.get("phase"),
                "from": branch.get("from"),
                "to": branch.get("to"),
                "status": branch.get("status"),
                "points": pts,
                "pixels": pixels,
                "provenance": session["provenance"].get("liquidus", {}).get(str(i), "auto"),
            }
        )

    immiscibility = None
    dome = draft.get("liquidImmiscibility") or {}
    boundary = dome.get("boundary") or []
    if boundary:
        pixels = []
        for pt in boundary:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            page_xy = axes.to_pixel(float(pt[0]), float(pt[1]))
            pixels.append(_page_to_image_pixel(page_xy, page_origin=origin))  # type: ignore[arg-type]
        immiscibility = {"pixels": pixels, "region": dome.get("region")}

    return {
        "diagramKind": "binary",
        "components": components,
        "xComponent": axes.x_component,
        "cornersImage": [],
        "points": points,
        "nodes": [],
        "boundaries": [],
        "isotherms": [],
        "liquidus": liquidus,
        "immiscibility": immiscibility,
    }


def _build_view(session: dict[str, Any]) -> dict[str, Any]:
    """Pixel-space view model for the SPA canvas."""
    draft = session["draft"]
    if is_binary_draft(draft):
        return _build_binary_view(session)

    components = draft["components"]
    calibration = draft.get("digitization", {}).get("calibration") or {}
    if not isinstance(calibration, dict):
        raise ValueError(f"{session.get('systemId')}: ternary draft needs digitization.calibration corners")
    corners = corners_from_calibration(components, calibration)
    origin = tuple(session["image"]["pageOrigin"])  # type: ignore[arg-type]
    stored_origin = session.get("pixelOrigin") or draft.get("digitization", {}).get("storedPixelOrigin") or [0, 0]
    cfg_origin = (float(stored_origin[0]), float(stored_origin[1]))

    points = []
    for inv in draft.get("invariantPoints", []):
        wt = [inv["liquid_wt"][c] for c in components]
        pix = polyline_wt_to_image_pixels([wt], corners=corners, origin=origin, components=components)[0]
        src = (inv.get("sources") or [{}])[0]
        points.append(
            {
                "id": inv["id"],
                "kind": "invariant",
                "temperature_C": inv.get("temperature_C"),
                "composition": {c: inv["liquid_wt"][c] for c in components},
                "wt": wt,
                "pixel": pix,
                "pagePixel": src.get("pixel"),
                "provenance": session["provenance"].get("points", {}).get(inv["id"], "auto"),
            }
        )

    # pd-nodes map (junctions, edges, rings, …) — selectable / deletable points
    # Prefer wt% → draft calibration so nodes stay aligned when they were digitized
    # against starts/candidates while the open draft is auto-full (different corner fit).
    nodes_view = []
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
        nodes_view.append(
            {
                "id": node.get("label") or node.get("id") or f"node-{node_index}",
                "nodeIndex": node_index,
                "kind": node.get("kind") or "junction",
                "label": node.get("label"),
                "wt": wt,
                "invariant": node.get("invariant"),
                "pixel": pix,
                "storedPixel": stored,
            }
        )

    boundaries = []
    for i, bc in enumerate(draft.get("boundaryCurves", [])):
        poly = bc.get("polyline_wt") or []
        pixels = polyline_wt_to_image_pixels(poly, corners=corners, origin=origin, components=components)
        arrows = bc.get("arrows")
        if arrows is None:
            arrows = _default_arrows(list(bc.get("path") or []))
            # If path is short but polyline has many points, one arrow mid-curve
            if not arrows and len(poly) >= 2:
                arrows = ["?"]
        boundaries.append(
            {
                "id": f"boundary-{i}",
                "index": i,
                "fields": bc.get("fields"),
                "path": bc.get("path"),
                "dashed": bool(bc.get("dashed")),
                "arrows": arrows,
                "polyline_wt": poly,
                "pixels": pixels,
                "provenance": session["provenance"].get("boundaries", {}).get(str(i), "auto"),
            }
        )

    isotherms = []
    for i, iso in enumerate(draft.get("isotherms", [])):
        poly = iso.get("polyline_wt") or []
        controls = iso.get("control_wt") or []
        # If only dense polyline exists, expose sparse handles for editing
        if not controls and poly:
            # ~10–14 handles so bends survive; CR then fills between them
            step = max(1, (len(poly) - 1) // 12)
            controls = [poly[j] for j in range(0, len(poly), step)]
            if controls[-1] != poly[-1]:
                controls.append(poly[-1])
            iso["control_wt"] = controls
            if len(controls) >= 2:
                iso["polyline_wt"] = rebuild_smooth_from_control_wt(
                    controls, corners=corners, origin=origin  # type: ignore[arg-type]
                )
                poly = iso["polyline_wt"]
        # Heal scrambled control order (nearest-neighbor path) then rebuild
        if controls and len(controls) >= 3:
            healed = heal_control_wt_order(
                controls, corners=corners, origin=origin  # type: ignore[arg-type]
            )
            if healed is not None:
                controls = healed
                iso["control_wt"] = controls
                iso["polyline_wt"] = rebuild_smooth_from_control_wt(
                    controls, corners=corners, origin=origin  # type: ignore[arg-type]
                )
                poly = iso["polyline_wt"]
        # Always draw via image-space CR through controls (not raw wt chords)
        if controls and len(controls) >= 2:
            control_pixels, pixels = control_wt_to_smooth_image_pixels(
                controls,
                corners=corners,
                origin=origin,  # type: ignore[arg-type]
                samples_per_segment=36,
            )
        else:
            pixels = polyline_wt_to_image_pixels(poly, corners=corners, origin=origin, components=components)
            control_pixels = polyline_wt_to_image_pixels(
                controls, corners=corners, origin=origin, components=components
            )
        isotherms.append(
            {
                "id": f"isotherm-{i}",
                "index": i,
                "field": iso.get("field"),
                "temperature_C": iso.get("temperature_C"),
                "dashed": bool(iso.get("dashed")),
                "closed": bool(iso.get("closed")),
                "polyline_wt": poly,
                "control_wt": controls,
                "pixels": pixels,
                "controls": control_pixels,
                "provenance": session["provenance"].get("isotherms", {}).get(str(i), "auto"),
            }
        )

    return {
        "diagramKind": "ternary",
        "components": components,
        "cornersImage": polyline_wt_to_image_pixels(
            [[100, 0, 0], [0, 100, 0], [0, 0, 100]],
            corners=corners,
            origin=origin,
            components=components,
        ),
        "points": points,
        "nodes": nodes_view,
        "boundaries": boundaries,
        "isotherms": isotherms,
        "liquidus": [],
    }


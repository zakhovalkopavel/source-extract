"""Invariant and node edit operations."""

from __future__ import annotations

from typing import Any

from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt
from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft
from source_extract.review.session_common import _corners_origin
from source_extract.review.session_persist import _push_undo, save_session
from source_extract.review.contour_point_helpers import _mover_identity


def move_invariant(
    session: dict[str, Any],
    *,
    point_id: str,
    image_pixel: list[float],
) -> dict[str, Any]:
    """Move an invariant; co-located curve vertices move with it (no reorder)."""
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

    mover = _mover_identity(type="invariant", id=point_id)
    old_pixel = _pixel_of_mover(session, mover)
    if old_pixel is None:
        raise KeyError(f"Invariant {point_id} not found")

    pixel = list(image_pixel)
    landmark = snap_image_to_existing_landmark(
        session, pixel, radius_px=IMAGE_POINT_TOL_PX
    )
    if landmark is not None:
        pixel = landmark
    else:
        snapped = snap_image_to_nearest_boundary(session, pixel)
        if snapped is not None:
            pixel = snapped

    session["_lastMoveNote"] = finish_topology_move(
        session, mover=mover, old_pixel=old_pixel, new_pixel=pixel
    )
    save_session(session)
    return session


def move_node(
    session: dict[str, Any],
    *,
    node_index: int,
    image_pixel: list[float],
) -> dict[str, Any]:
    """Move a pd-node; shared co-located points move with it."""
    _push_undo(session)
    nodes = session.get("nodes") or []
    if node_index < 0 or node_index >= len(nodes):
        raise IndexError(f"Node index {node_index} out of range")
    from source_extract.review.isotherm_boundary_snap import (
        IMAGE_POINT_TOL_PX,
        snap_image_to_existing_landmark,
        snap_image_to_nearest_boundary,
    )
    from source_extract.review.point_topology import (
        _pixel_of_mover,
        finish_topology_move,
    )

    mover = _mover_identity(type="node", index=node_index)
    old_pixel = _pixel_of_mover(session, mover)
    pixel = list(image_pixel)
    landmark = snap_image_to_existing_landmark(
        session, pixel, radius_px=IMAGE_POINT_TOL_PX
    )
    if landmark is not None:
        pixel = landmark
    else:
        snapped = snap_image_to_nearest_boundary(session, pixel)
        if snapped is not None:
            pixel = snapped

    session["_lastMoveNote"] = finish_topology_move(
        session, mover=mover, old_pixel=old_pixel, new_pixel=pixel
    )
    save_session(session)
    return session


def _point_role(*, point_id: str, notation: str | None, compound_id: str | None) -> str:
    """``compound`` when named (formula / compounds.json); else generic ``invariant``."""
    if notation or compound_id:
        return "compound"
    from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag

    enrich = enrich_invariant_from_tag(point_id)
    if enrich.get("notation") or enrich.get("compoundId"):
        return "compound"
    return "invariant"


def ensure_invariant_from_node(
    session: dict[str, Any],
    *,
    node_index: int,
) -> dict[str, Any]:
    """Promote a compound ring (C#) into a draft invariant so it edits like I#.

    Idempotent: if the node already links to an invariant, only records the id.
    Rings default to ``pointRole=compound``; other promoted nodes stay ``invariant``.
    """
    nodes = session.get("nodes") or []
    if node_index < 0 or node_index >= len(nodes):
        raise IndexError(f"Node index {node_index} out of range")
    node = nodes[node_index]
    linked = node.get("invariant")
    invs = session["draft"].setdefault("invariantPoints", [])
    if linked and any(p.get("id") == linked for p in invs):
        session["_lastNodeEnsure"] = {
            "nodeIndex": node_index,
            "id": linked,
            "created": False,
            "pointRole": next(
                (
                    p.get("pointRole")
                    or _point_role(
                        point_id=str(p["id"]),
                        notation=(p.get("sources") or [{}])[0].get("notation"),
                        compound_id=(p.get("sources") or [{}])[0].get("compoundId"),
                    )
                    for p in invs
                    if p.get("id") == linked
                ),
                "invariant",
            ),
        }
        return session

    label = str(node.get("label") or "").strip()
    kind = str(node.get("kind") or "")
    components = list(session["draft"]["components"])
    wt_list = node.get("wt")
    if isinstance(wt_list, (list, tuple)) and len(wt_list) == len(components):
        liquid_wt = {c: round(float(wt_list[i]), 2) for i, c in enumerate(components)}
    else:
        # Fall back to pixel → wt
        from source_extract.review.nodes_attach import _stored_to_image_pixel

        components, corners, origin = _corners_origin(session)
        stored_origin = session.get("pixelOrigin") or session["draft"].get("digitization", {}).get(
            "storedPixelOrigin"
        ) or [0, 0]
        cfg = (float(stored_origin[0]), float(stored_origin[1]))
        stored = node.get("pixel") or [0, 0]
        img = _stored_to_image_pixel(
            stored, pixel_origin=cfg, page_origin=origin  # type: ignore[arg-type]
        )
        page = image_to_page_pixel((img[0], img[1]), origin)  # type: ignore[arg-type]
        wt = page_pixel_to_wt(page, corners)
        liquid_wt = {c: round(float(wt[i]), 2) for i, c in enumerate(components)}

    pid = label or f"node-{node_index}"
    # Avoid colliding with an existing id unless this node already owns it
    if any(p.get("id") == pid for p in invs):
        pid = f"{pid}-ring" if kind == "ring" else f"{pid}-{node_index}"

    from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag

    enrich = enrich_invariant_from_tag(pid)
    notation = enrich.get("notation")
    compound_id = enrich.get("compoundId")
    temperature_C = enrich.get("temperature_C")
    phases = list(enrich.get("phases") or [])
    point_role = "compound" if kind == "ring" else _point_role(
        point_id=pid, notation=notation, compound_id=compound_id
    )
    if point_role == "compound" and not notation and label:
        notation = label

    _push_undo(session)
    from source_extract.review.retrace import polyline_wt_to_image_pixels

    components, corners, origin = _corners_origin(session)
    img = polyline_wt_to_image_pixels(
        [[float(liquid_wt[c]) for c in components]],
        corners=corners,
        origin=origin,  # type: ignore[arg-type]
        components=components,
    )[0]
    page = image_to_page_pixel((img[0], img[1]), origin)  # type: ignore[arg-type]
    entry: dict[str, Any] = {
        "id": pid,
        "type": "ternary" if len(components) == 3 else "binary",
        "pointRole": point_role,
        "reaction": "compound" if point_role == "compound" else "unknown",
        "phases": phases,
        "temperature_C": float(temperature_C) if temperature_C is not None else None,
        "liquid_wt": liquid_wt,
        "notation": notation,
        "status": "user",
        "sources": [
            {
                "ref": "source-extract-review",
                "composition": "from-node",
                "temperature": "compound-data" if temperature_C is not None else None,
                "compoundId": compound_id,
                "notation": notation,
                "pixel": [round(float(page[0]), 1), round(float(page[1]), 1)],
                "fromNode": node_index,
                "fromNodeLabel": label or None,
            }
        ],
    }
    invs.append(entry)
    node["invariant"] = pid
    session["nodes"] = nodes
    session["provenance"].setdefault("points", {})[pid] = "user"
    for name in phases:
        if name and name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(name)
    session["_lastNodeEnsure"] = {
        "nodeIndex": node_index,
        "id": pid,
        "created": True,
        "pointRole": point_role,
    }
    save_session(session)
    return session


def delete_invariant(session: dict[str, Any], *, point_id: str) -> dict[str, Any]:
    _push_undo(session)
    before = len(session["draft"]["invariantPoints"])
    session["draft"]["invariantPoints"] = [p for p in session["draft"]["invariantPoints"] if p["id"] != point_id]
    if len(session["draft"]["invariantPoints"]) == before:
        raise KeyError(f"Invariant {point_id} not found")
    session["provenance"]["points"].pop(point_id, None)
    save_session(session)
    return session


def add_invariant(
    session: dict[str, Any],
    *,
    point_id: str,
    image_pixel: list[float],
    temperature_C: float | None = None,
    phases: list[str] | None = None,
    reaction: str | None = None,
) -> dict[str, Any]:
    """Place a new invariant (e.g. missing A3S2 / cas-1385) at an image pixel.

    Saved immediately on place — no separate Save step.
    """
    invs = session["draft"].setdefault("invariantPoints", [])
    pid = str(point_id or "").strip()
    if not pid:
        # Place-first UX: create a provisional id; user renames in the edit panel.
        n = 1
        existing = {str(p.get("id") or "") for p in invs}
        while f"pt-{n}" in existing:
            n += 1
        pid = f"pt-{n}"
    elif any(p.get("id") == pid for p in invs):
        raise ValueError(f"Invariant '{pid}' already exists")
    from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag

    enrich = enrich_invariant_from_tag(pid)
    if temperature_C is None and enrich.get("temperature_C") is not None:
        temperature_C = float(enrich["temperature_C"])
    if not phases and enrich.get("phases"):
        phases = list(enrich["phases"])
    _push_undo(session)
    draft = session["draft"]
    components = list(draft["components"])
    origin = tuple(session["image"]["pageOrigin"])
    page = (float(image_pixel[0]) + float(origin[0]), float(image_pixel[1]) + float(origin[1]))
    if is_binary_draft(draft):
        axes = axes_from_digitization(draft)
        if axes is None:
            raise ValueError("Binary draft has no axes calibration — run Analyze / pd-extract")
        x_wt, t_read = axes.to_data(*page)
        liquid_wt = {
            axes.x_component: round(float(x_wt), 2),
            axes.other_component: round(100.0 - float(x_wt), 2),
        }
        liquid_wt = {c: liquid_wt.get(c, 0.0) for c in components}
        if temperature_C is None:
            temperature_C = float(t_read)
    else:
        components, corners, _origin = _corners_origin(session)
        from source_extract.review.barycentric import page_pixel_to_wt

        wt = page_pixel_to_wt(page, corners)
        liquid_wt = {c: round(float(wt[i]), 2) for i, c in enumerate(components)}
    phase_list = [p for p in (phases or []) if p]
    for name in phase_list:
        if name not in session["draft"].setdefault("phases", []):
            session["draft"]["phases"].append(name)
    temp_source = None
    if temperature_C is not None:
        temp_source = "compound-data" if enrich.get("temperature_C") is not None else "user"
    notation = enrich.get("notation")
    compound_id = enrich.get("compoundId")
    point_role = _point_role(point_id=pid, notation=notation, compound_id=compound_id)
    entry: dict[str, Any] = {
        "id": pid,
        "type": "ternary" if len(components) == 3 else "binary",
        "pointRole": point_role,
        "reaction": reaction
        or ("compound" if point_role == "compound" else "unknown"),
        "phases": phase_list,
        "temperature_C": float(temperature_C) if temperature_C is not None else None,
        "liquid_wt": liquid_wt,
        "notation": notation,
        "status": "user",
        "sources": [
            {
                "ref": "source-extract-review",
                "composition": "digitized",
                "temperature": temp_source,
                "compoundId": compound_id,
                "notation": notation,
                "pixel": [round(float(page[0]), 1), round(float(page[1]), 1)],
            }
        ],
    }
    invs.append(entry)
    session["provenance"].setdefault("points", {})[pid] = "user"
    session["_lastInvariantLookup"] = {
        "id": pid,
        "compoundId": enrich.get("compoundId"),
        "notation": enrich.get("notation"),
        "temperature_C": temperature_C,
        "resolved": bool(enrich),
    }
    save_session(session)
    return session


def update_invariant(
    session: dict[str, Any],
    *,
    point_id: str,
    temperature_C: float | None = None,
    phases: list[str] | None = None,
    reaction: str | None = None,
    new_id: str | None = None,
    set_temperature: bool = False,
    point_role: str | None = None,
) -> dict[str, Any]:
    """Update metadata on an existing invariant (temperature / id / phases / type).

    Pass ``set_temperature=True`` to apply ``temperature_C`` even when it is ``None``
    (clears °C). When ``set_temperature`` is false, temperature is left unchanged.
    """
    invs = session["draft"].setdefault("invariantPoints", [])
    idx = next((i for i, p in enumerate(invs) if p.get("id") == point_id), None)
    if idx is None:
        raise KeyError(f"Invariant {point_id} not found")
    _push_undo(session)
    inv = invs[idx]
    if new_id is not None:
        nid = str(new_id).strip()
        if not nid:
            raise ValueError("Invariant id cannot be empty")
        if nid != point_id and any(p.get("id") == nid for p in invs):
            raise ValueError(f"Invariant '{nid}' already exists")
        old = inv["id"]
        inv["id"] = nid
        prov = session["provenance"].setdefault("points", {})
        if old in prov:
            prov[nid] = prov.pop(old)
        else:
            prov[nid] = "user"
    if set_temperature:
        inv["temperature_C"] = None if temperature_C is None else float(temperature_C)
        inv["status"] = "user"
    if phases is not None:
        phase_list = [p for p in phases if p]
        inv["phases"] = phase_list
        for name in phase_list:
            if name not in session["draft"].setdefault("phases", []):
                session["draft"]["phases"].append(name)
    if reaction is not None:
        inv["reaction"] = reaction or None
    src0 = (inv.get("sources") or [{}])[0]
    if point_role in ("compound", "invariant"):
        inv["pointRole"] = point_role
    else:
        # Infer from name / compounds.json when the user did not set a type.
        inv["pointRole"] = _point_role(
            point_id=str(inv["id"]),
            notation=inv.get("notation") or src0.get("notation"),
            compound_id=src0.get("compoundId"),
        )
    if inv["pointRole"] == "compound" and inv.get("reaction") in (None, "", "unknown"):
        inv["reaction"] = "compound"
    session["provenance"].setdefault("points", {})[str(inv["id"])] = "user"
    save_session(session)
    return session


def reposition_invariants_from_wt(session: dict[str, Any]) -> dict[str, Any]:
    """Rewrite each invariant ``sources[].pixel`` from ``liquid_wt`` (page space).

    Snaps markers onto the triangle from stored compositions. Does not re-run Analyze
    / topology search. One undo step.
    """
    if not session.get("draft", {}).get("invariantPoints"):
        return session
    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    from source_extract.review.retrace import polyline_wt_to_image_pixels

    n = 0
    for inv in session["draft"]["invariantPoints"]:
        wt = [float(inv["liquid_wt"][c]) for c in components]
        img = polyline_wt_to_image_pixels(
            [wt], corners=corners, origin=origin, components=components  # type: ignore[arg-type]
        )[0]
        page = image_to_page_pixel((img[0], img[1]), origin)  # type: ignore[arg-type]
        sources = inv.setdefault("sources", [{}])
        if not sources:
            sources.append({})
            inv["sources"] = sources
        sources[0]["pixel"] = [round(float(page[0]), 1), round(float(page[1]), 1)]
        sources[0]["composition"] = sources[0].get("composition") or "from-wt"
        n += 1
    session["_lastInvariantReposition"] = {"count": n}
    save_session(session)
    return session


"""Invariant and node edit operations."""

from __future__ import annotations

from typing import Any

from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt
from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft
from source_extract.review.session_common import _corners_origin
from source_extract.review.session_persist import _push_undo, save_session
from source_extract.review.contour_point_helpers import _finish_move_coalesce, _mover_identity


def move_invariant(
    session: dict[str, Any],
    *,
    point_id: str,
    image_pixel: list[float],
) -> dict[str, Any]:
    _push_undo(session)
    components, corners, origin = _corners_origin(session)
    from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt

    page = image_to_page_pixel((image_pixel[0], image_pixel[1]), origin)  # type: ignore[arg-type]
    wt = page_pixel_to_wt(page, corners)
    for inv in session["draft"]["invariantPoints"]:
        if inv["id"] != point_id:
            continue
        inv["liquid_wt"] = {c: wt[i] for i, c in enumerate(components)}
        sources = inv.setdefault("sources", [{}])
        if sources:
            sources[0]["pixel"] = [round(page[0], 1), round(page[1], 1)]
        session["provenance"]["points"][point_id] = "user"
        break
    else:
        raise KeyError(f"Invariant {point_id} not found")
    session["_lastMoveNote"] = _finish_move_coalesce(
        session,
        mover=_mover_identity(type="invariant", id=point_id),
        image_pixel=image_pixel,
    )
    save_session(session)
    return session


def move_node(
    session: dict[str, Any],
    *,
    node_index: int,
    image_pixel: list[float],
) -> dict[str, Any]:
    """Move a pd-node in image pixels; updates stored pixel + wt%."""
    _push_undo(session)
    nodes = session.get("nodes") or []
    if node_index < 0 or node_index >= len(nodes):
        raise IndexError(f"Node index {node_index} out of range")
    components, corners, origin = _corners_origin(session)
    from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt

    page = image_to_page_pixel((image_pixel[0], image_pixel[1]), origin)  # type: ignore[arg-type]
    wt = page_pixel_to_wt(page, corners)
    stored_origin = session.get("pixelOrigin") or session["draft"].get("digitization", {}).get(
        "storedPixelOrigin"
    ) or [0, 0]
    cfg = (float(stored_origin[0]), float(stored_origin[1]))
    # Inverse of _stored_to_image_pixel
    stored = [
        round(float(image_pixel[0]) - cfg[0] + float(origin[0]), 2),
        round(float(image_pixel[1]) - cfg[1] + float(origin[1]), 2),
    ]
    nodes[node_index]["pixel"] = stored
    nodes[node_index]["wt"] = [round(float(v), 2) for v in wt]
    session["nodes"] = nodes
    session["_lastMoveNote"] = _finish_move_coalesce(
        session,
        mover=_mover_identity(type="node", index=node_index),
        image_pixel=image_pixel,
    )
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
    pid = str(point_id or "").strip()
    if not pid:
        raise ValueError("Invariant id is required")
    invs = session["draft"].setdefault("invariantPoints", [])
    if any(p.get("id") == pid for p in invs):
        raise ValueError(f"Invariant '{pid}' already exists")
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
    entry: dict[str, Any] = {
        "id": pid,
        "type": "ternary" if len(components) == 3 else "binary",
        "reaction": reaction or "unknown",
        "phases": phase_list,
        "temperature_C": float(temperature_C) if temperature_C is not None else None,
        "liquid_wt": liquid_wt,
        "status": "user",
        "sources": [
            {
                "ref": "source-extract-review",
                "composition": "digitized",
                "temperature": "user" if temperature_C is not None else None,
                "pixel": [round(float(page[0]), 1), round(float(page[1]), 1)],
            }
        ],
    }
    invs.append(entry)
    session["provenance"].setdefault("points", {})[pid] = "user"
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
) -> dict[str, Any]:
    """Update metadata on an existing invariant (temperature / id / phases)."""
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
    if temperature_C is not None:
        inv["temperature_C"] = float(temperature_C)
        inv["status"] = "user"
    if phases is not None:
        phase_list = [p for p in phases if p]
        inv["phases"] = phase_list
        for name in phase_list:
            if name not in session["draft"].setdefault("phases", []):
                session["draft"]["phases"].append(name)
    if reaction is not None:
        inv["reaction"] = reaction
    session["provenance"].setdefault("points", {})[str(inv["id"])] = "user"
    save_session(session)
    return session


"""Shared-point topology: priority replace, cluster moves, curve join, normalize.

Priority (high → low): compound > invariant > simple.
Frame / calibration corners are never deleted.

Moving a point moves every landmark that already shared its old position.
Landing near a curve (within tolerance) inserts a control between the two
nearest segment endpoints — move never reorders existing controls.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from source_extract.review.barycentric import image_to_page_pixel, page_pixel_to_wt
from source_extract.review.contour_point_helpers import (
    POINT_COALESCE_RADIUS_PX,
    _delete_invariant_no_undo,
    _delete_node_no_undo,
    _delete_point_no_undo,
    _is_same_point,
    _list_discrete_landmarks,
    _mover_identity,
    _nearest_segment_index,
)
from source_extract.review.retrace import (
    polyline_wt_to_image_pixels,
    rebuild_smooth_from_control_wt,
)
from source_extract.review.session_common import _corners_origin
from source_extract.review.session_persist import _push_undo, save_session

# compound=30, invariant=20, simple=10, frame=100 (immortal)
PRIORITY_FRAME = 100
PRIORITY_COMPOUND = 30
PRIORITY_INVARIANT = 20
PRIORITY_SIMPLE = 10


def _inv_by_id(session: dict[str, Any], point_id: str) -> dict[str, Any] | None:
    for inv in session["draft"].get("invariantPoints") or []:
        if inv.get("id") == point_id:
            return inv
    return None


def _is_compound_inv(inv: dict[str, Any] | None) -> bool:
    if not inv:
        return False
    if inv.get("pointRole") == "compound":
        return True
    if inv.get("compoundId") or inv.get("notation"):
        return True
    from source_extract.review.invariant_compound_lookup import enrich_invariant_from_tag

    enrich = enrich_invariant_from_tag(str(inv.get("id") or ""))
    return bool(enrich.get("resolved") and (enrich.get("compoundId") or enrich.get("notation")))


def landmark_priority(session: dict[str, Any], loc: dict[str, Any]) -> int:
    """Higher number wins replace conflicts."""
    t = loc.get("type")
    if t == "frame":
        return PRIORITY_FRAME
    if t == "invariant":
        inv = _inv_by_id(session, str(loc.get("id") or ""))
        return PRIORITY_COMPOUND if _is_compound_inv(inv) else PRIORITY_INVARIANT
    if t == "node":
        nodes = session.get("nodes") or []
        idx = int(loc.get("index", -1))
        node = nodes[idx] if 0 <= idx < len(nodes) else {}
        kind = str(node.get("kind") or loc.get("kind") or "")
        if kind == "corner":
            return PRIORITY_FRAME
        linked = node.get("invariant")
        if kind == "ring" or (isinstance(linked, str) and linked):
            inv = _inv_by_id(session, str(linked)) if linked else None
            if _is_compound_inv(inv) or kind == "ring":
                # Rings default to compound-class when named; plain linked inv → invariant.
                if inv is not None:
                    return (
                        PRIORITY_COMPOUND if _is_compound_inv(inv) else PRIORITY_INVARIANT
                    )
                from source_extract.review.invariant_compound_lookup import (
                    enrich_invariant_from_tag,
                )

                enrich = enrich_invariant_from_tag(str(linked or node.get("label") or ""))
                if enrich.get("resolved"):
                    return PRIORITY_COMPOUND
                return PRIORITY_INVARIANT if kind == "invariant" else PRIORITY_COMPOUND
        if kind == "invariant":
            return PRIORITY_INVARIANT
        return PRIORITY_SIMPLE
    # Curve vertex = simple geometry anchor (kept for sharing, but loses identity).
    return PRIORITY_SIMPLE


def _pixel_of_mover(session: dict[str, Any], mover: dict[str, Any]) -> list[float] | None:
    for loc in _list_discrete_landmarks(session):
        if _is_same_point(mover, loc):
            return [float(loc["x"]), float(loc["y"])]
    return None


def cluster_at(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    radius_px: float = POINT_COALESCE_RADIUS_PX,
) -> list[dict[str, Any]]:
    """All discrete landmarks within ``radius_px`` of ``image_pixel``."""
    px, py = float(image_pixel[0]), float(image_pixel[1])
    r2 = radius_px * radius_px
    out: list[dict[str, Any]] = []
    for loc in _list_discrete_landmarks(session):
        dx = float(loc["x"]) - px
        dy = float(loc["y"]) - py
        if dx * dx + dy * dy <= r2:
            out.append(loc)
    return out


def _set_landmark_wt(
    session: dict[str, Any],
    loc: dict[str, Any],
    wt: Sequence[float],
    *,
    page: Sequence[float],
    image_pixel: Sequence[float],
) -> None:
    """Write composition / pixel onto a landmark **without** reordering curves."""
    components, corners, origin = _corners_origin(session)
    t = loc.get("type")
    if t == "frame":
        return  # calibration corners moved only via dedicated API
    if t == "invariant":
        inv = _inv_by_id(session, str(loc.get("id") or ""))
        if not inv:
            return
        inv["liquid_wt"] = {c: float(wt[i]) for i, c in enumerate(components)}
        sources = inv.setdefault("sources", [{}])
        if sources:
            sources[0]["pixel"] = [round(float(page[0]), 1), round(float(page[1]), 1)]
        session.setdefault("provenance", {}).setdefault("points", {})[str(inv["id"])] = "user"
        return
    if t == "node":
        nodes = session.get("nodes") or []
        idx = int(loc["index"])
        if not (0 <= idx < len(nodes)):
            return
        stored_origin = session.get("pixelOrigin") or session["draft"].get(
            "digitization", {}
        ).get("storedPixelOrigin") or [0, 0]
        cfg = (float(stored_origin[0]), float(stored_origin[1]))
        nodes[idx]["wt"] = [round(float(v), 2) for v in wt]
        nodes[idx]["pixel"] = [
            round(float(image_pixel[0]) - cfg[0] + float(origin[0]), 2),
            round(float(image_pixel[1]) - cfg[1] + float(origin[1]), 2),
        ]
        session["nodes"] = nodes
        return
    if t == "vertex":
        kind = loc.get("kind")
        cidx = int(loc["index"])
        pidx = int(loc["pointIndex"])
        wt_list = [round(float(v), 2) for v in wt]
        if kind == "boundary":
            bc = session["draft"]["boundaryCurves"][cidx]
            controls = list(bc.get("control_wt") or [])
            if controls and 0 <= pidx < len(controls):
                controls[pidx] = wt_list
                bc["control_wt"] = controls
                bc["polyline_wt"] = rebuild_smooth_from_control_wt(
                    controls, corners=corners, origin=origin  # type: ignore[arg-type]
                )
            else:
                poly = bc.get("polyline_wt") or []
                if 0 <= pidx < len(poly):
                    poly[pidx] = wt_list
            session.setdefault("provenance", {}).setdefault("boundaries", {})[str(cidx)] = "user"
        elif kind == "isotherm":
            iso = session["draft"]["isotherms"][cidx]
            controls = list(iso.get("control_wt") or iso.get("polyline_wt") or [])
            if 0 <= pidx < len(controls):
                controls[pidx] = wt_list
                iso["control_wt"] = controls
                iso["polyline_wt"] = rebuild_smooth_from_control_wt(
                    controls, corners=corners, origin=origin  # type: ignore[arg-type]
                )
                session.setdefault("provenance", {}).setdefault("isotherms", {})[
                    str(cidx)
                ] = "user"


def apply_cluster_position(
    session: dict[str, Any],
    cluster: Sequence[dict[str, Any]],
    image_pixel: Sequence[float],
) -> None:
    """Move every landmark in ``cluster`` to ``image_pixel`` (order preserved)."""
    components, corners, origin = _corners_origin(session)
    page = image_to_page_pixel((float(image_pixel[0]), float(image_pixel[1])), origin)  # type: ignore[arg-type]
    wt = page_pixel_to_wt(page, corners)
    for loc in cluster:
        if loc.get("type") == "frame":
            continue
        _set_landmark_wt(session, loc, wt, page=page, image_pixel=image_pixel)


def _curve_has_control_near(
    session: dict[str, Any],
    *,
    kind: str,
    index: int,
    image_pixel: Sequence[float],
    radius_px: float,
) -> bool:
    for loc in cluster_at(session, image_pixel, radius_px=radius_px):
        if (
            loc.get("type") == "vertex"
            and loc.get("kind") == kind
            and int(loc.get("index", -1)) == index
        ):
            return True
    return False


def _ensure_control_on_curve(
    session: dict[str, Any],
    *,
    kind: str,
    index: int,
    image_pixel: Sequence[float],
    radius_px: float = POINT_COALESCE_RADIUS_PX,
) -> bool:
    """Insert a control between the nearest segment's endpoints if none nearby.

    Does not reorder existing controls — only inserts.
    """
    if _curve_has_control_near(
        session, kind=kind, index=index, image_pixel=image_pixel, radius_px=radius_px
    ):
        return False
    components, corners, origin = _corners_origin(session)
    page = image_to_page_pixel((float(image_pixel[0]), float(image_pixel[1])), origin)  # type: ignore[arg-type]
    wt = [round(float(v), 2) for v in page_pixel_to_wt(page, corners)]

    if kind == "boundary":
        bc = session["draft"]["boundaryCurves"][index]
        controls = list(bc.get("control_wt") or [])
        if not controls:
            poly = list(bc.get("polyline_wt") or [])
            if len(poly) < 2:
                return False
            step = max(1, (len(poly) - 1) // 12)
            controls = [poly[j] for j in range(0, len(poly), step)]
            if controls[-1] != poly[-1]:
                controls.append(poly[-1])
        ctrl_img = polyline_wt_to_image_pixels(
            controls, corners=corners, origin=origin, components=components
        )
        # Distance to curve must be within tolerance.
        after = _nearest_segment_index(list(image_pixel), ctrl_img)
        a = ctrl_img[after]
        b = ctrl_img[min(after + 1, len(ctrl_img) - 1)]
        # Project distance
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        px, py = float(image_pixel[0]), float(image_pixel[1])
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy or 1.0
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
        qx, qy = ax + t * dx, ay + t * dy
        if math.hypot(px - qx, py - qy) > radius_px * 4.5:
            return False
        controls.insert(after + 1, wt)
        bc["control_wt"] = controls
        bc["polyline_wt"] = rebuild_smooth_from_control_wt(
            controls, corners=corners, origin=origin  # type: ignore[arg-type]
        )
        session.setdefault("provenance", {}).setdefault("boundaries", {})[str(index)] = "user"
        return True

    if kind == "isotherm":
        iso = session["draft"]["isotherms"][index]
        controls = list(iso.get("control_wt") or iso.get("polyline_wt") or [])
        if len(controls) < 2:
            return False
        ctrl_img = polyline_wt_to_image_pixels(
            controls, corners=corners, origin=origin, components=components
        )
        after = _nearest_segment_index(list(image_pixel), ctrl_img)
        a = ctrl_img[after]
        b = ctrl_img[min(after + 1, len(ctrl_img) - 1)]
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        px, py = float(image_pixel[0]), float(image_pixel[1])
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy or 1.0
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
        qx, qy = ax + t * dx, ay + t * dy
        if math.hypot(px - qx, py - qy) > radius_px * 4.5:
            return False
        controls.insert(after + 1, wt)
        iso["control_wt"] = controls
        iso["polyline_wt"] = rebuild_smooth_from_control_wt(
            controls, corners=corners, origin=origin  # type: ignore[arg-type]
        )
        session.setdefault("provenance", {}).setdefault("isotherms", {})[str(index)] = "user"
        return True
    return False


def join_nearby_curves(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    radius_px: float = POINT_COALESCE_RADIUS_PX,
) -> int:
    """Ensure every nearby boundary/isotherm has a control at ``image_pixel``."""
    from source_extract.review.isotherm_boundary_snap import _project_onto_polyline

    components, corners, origin = _corners_origin(session)
    joined = 0
    # Wider radius for "on the line" — same as isotherm-boundary snap.
    line_tol = radius_px * 4.5
    for i, bc in enumerate(session["draft"].get("boundaryCurves") or []):
        poly = bc.get("control_wt") or bc.get("polyline_wt") or []
        if len(poly) < 2:
            continue
        pix = polyline_wt_to_image_pixels(
            poly if bc.get("control_wt") else poly,
            corners=corners,
            origin=origin,
            components=components,
        )
        # Prefer dense polyline for distance-to-curve when available.
        dense = bc.get("polyline_wt") or poly
        dense_img = polyline_wt_to_image_pixels(
            dense, corners=corners, origin=origin, components=components
        )
        hit = _project_onto_polyline(image_pixel, dense_img)
        if hit is None or hit[1] > line_tol:
            continue
        if _ensure_control_on_curve(
            session, kind="boundary", index=i, image_pixel=image_pixel, radius_px=radius_px
        ):
            joined += 1
    for i, iso in enumerate(session["draft"].get("isotherms") or []):
        controls = iso.get("control_wt") or iso.get("polyline_wt") or []
        if len(controls) < 2:
            continue
        dense = iso.get("polyline_wt") or controls
        dense_img = polyline_wt_to_image_pixels(
            dense, corners=corners, origin=origin, components=components
        )
        hit = _project_onto_polyline(image_pixel, dense_img)
        if hit is None or hit[1] > line_tol:
            continue
        if _ensure_control_on_curve(
            session, kind="isotherm", index=i, image_pixel=image_pixel, radius_px=radius_px
        ):
            joined += 1
    return joined


def resolve_priority_at(
    session: dict[str, Any],
    image_pixel: Sequence[float],
    *,
    mover: dict[str, Any],
    radius_px: float = POINT_COALESCE_RADIUS_PX,
) -> str | None:
    """Keep highest-priority identity; drop lower named points; keep curve verts.

    Curve vertices are geometry and stay (shared). Simple nodes / lower invariants
    are removed. If mover loses to a higher identity, mover is removed.
    """
    cluster = cluster_at(session, image_pixel, radius_px=radius_px)
    if len(cluster) <= 1:
        return None

    ranked = sorted(
        cluster,
        key=lambda loc: (-landmark_priority(session, loc), loc.get("type") or ""),
    )
    winner = ranked[0]
    winner_p = landmark_priority(session, winner)
    notes: list[str] = []

    # If mover is not the winner and mover is named (inv/node), absorb mover.
    mover_in = next((c for c in cluster if _is_same_point(mover, c)), None)
    if mover_in is not None and not _is_same_point(mover, winner):
        mover_p = landmark_priority(session, mover_in)
        if mover_p < winner_p and mover.get("type") in ("invariant", "node"):
            if mover["type"] == "invariant":
                _delete_invariant_no_undo(session, str(mover["id"]))
            else:
                _delete_node_no_undo(session, int(mover["index"]))
            notes.append("absorbed into higher-priority point")
            # Refresh cluster after deletion
            cluster = cluster_at(session, image_pixel, radius_px=radius_px)
            ranked = sorted(
                cluster,
                key=lambda loc: (-landmark_priority(session, loc), loc.get("type") or ""),
            )
            winner = ranked[0]
            winner_p = landmark_priority(session, winner)

    removed = 0
    # Delete lower-priority named points (not curve vertices, not frame).
    to_delete = [
        loc
        for loc in cluster
        if not _is_same_point(loc, winner)
        and loc.get("type") in ("invariant", "node")
        and landmark_priority(session, loc) < winner_p
    ]
    # Same-curve duplicate vertices only
    same_curve_dups = [
        loc
        for loc in cluster
        if loc.get("type") == "vertex"
        and mover.get("type") == "vertex"
        and loc.get("kind") == mover.get("kind")
        and int(loc.get("index", -1)) == int(mover.get("index", -2))
        and not _is_same_point(loc, mover)
    ]
    # Sort high indices first
    to_delete_sorted = sorted(
        to_delete,
        key=lambda t: (0 if t["type"] == "invariant" else 1, -int(t.get("index", 0))),
    )
    for loc in to_delete_sorted:
        if loc["type"] == "invariant":
            _delete_invariant_no_undo(session, str(loc["id"]))
            removed += 1
        elif loc["type"] == "node":
            _delete_node_no_undo(session, int(loc["index"]))
            removed += 1
    for loc in sorted(
        same_curve_dups,
        key=lambda t: int(t["pointIndex"]),
        reverse=True,
    ):
        _delete_point_no_undo(
            session,
            contour_kind=loc["kind"],  # type: ignore[arg-type]
            contour_index=int(loc["index"]),
            point_index=int(loc["pointIndex"]),
        )
        removed += 1

    if removed:
        notes.append(f"replaced {removed} lower-priority point(s)")
    shared_curves = sum(1 for c in cluster if c.get("type") == "vertex")
    if shared_curves:
        notes.append(f"shared with {shared_curves} curve vertex(es)")
    return "; ".join(notes) if notes else None


def finish_topology_move(
    session: dict[str, Any],
    *,
    mover: dict[str, Any],
    old_pixel: Sequence[float] | None,
    new_pixel: Sequence[float],
) -> str | None:
    """Shared-cluster move + priority replace + join nearby curves. No reorder."""
    bits: list[str] = []
    # 1) Move everyone that shared the old position.
    if old_pixel is not None:
        old_cluster = cluster_at(session, old_pixel)
        # Ensure mover is in the cluster identity list even if listing lagged.
        apply_cluster_position(session, old_cluster, new_pixel)
        if len(old_cluster) > 1:
            bits.append(f"moved {len(old_cluster)} shared point(s)")

    # 2) Priority replace at the landing site.
    note = resolve_priority_at(session, new_pixel, mover=mover)
    if note:
        bits.append(note)

    # 3) Become part of nearby lines (insert control between nearest neighbours).
    joined = join_nearby_curves(session, new_pixel)
    if joined:
        bits.append(f"joined {joined} curve(s)")

    return "; ".join(bits) if bits else None


def normalize_points(session: dict[str, Any]) -> dict[str, Any]:
    """Coalesce every near-duplicate cluster by priority and join shared curves."""
    _push_undo(session)
    radius = POINT_COALESCE_RADIUS_PX
    visited: set[str] = set()
    clusters = 0
    replaced = 0
    joined_total = 0

    def key_of(loc: dict[str, Any]) -> str:
        if loc.get("type") == "invariant":
            return f"inv:{loc.get('id')}"
        if loc.get("type") == "node":
            return f"node:{loc.get('index')}"
        if loc.get("type") == "frame":
            return f"frame:{loc.get('index')}"
        return f"v:{loc.get('kind')}:{loc.get('index')}:{loc.get('pointIndex')}"

    # Iterate until stable (deletes change indices).
    for _ in range(8):
        landmarks = _list_discrete_landmarks(session)
        progressed = False
        for loc in landmarks:
            k = key_of(loc)
            if k in visited:
                continue
            cluster = cluster_at(session, [loc["x"], loc["y"]], radius_px=radius)
            if len(cluster) < 2:
                visited.add(k)
                continue
            clusters += 1
            # Anchor on highest-priority member.
            winner = max(cluster, key=lambda c: landmark_priority(session, c))
            pixel = [float(winner["x"]), float(winner["y"])]
            apply_cluster_position(session, cluster, pixel)
            mover = _mover_identity(
                type=str(winner.get("type")),
                id=winner.get("id"),
                index=winner.get("index"),
                kind=winner.get("kind"),
                point_index=winner.get("pointIndex"),
            )
            note = resolve_priority_at(session, pixel, mover=mover, radius_px=radius)
            if note and "replaced" in note:
                replaced += 1
                progressed = True
            joined_total += join_nearby_curves(session, pixel, radius_px=radius)
            for c in cluster:
                visited.add(key_of(c))
        if not progressed:
            break
        visited.clear()

    session["_lastNormalizePoints"] = {
        "clusters": clusters,
        "replaced": replaced,
        "joined": joined_total,
    }
    save_session(session)
    return session

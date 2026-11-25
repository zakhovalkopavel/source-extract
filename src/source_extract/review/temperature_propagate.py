"""Propagate isotherm °C to nearest neighbours after a manual temperature Save.

When the reviewer sets temperature on one isotherm, the closest curves on each
side of that curve should sit on opposite sides of the thermal gradient
(one hotter, one colder). Direction is inferred from other isotherms that
already have temperatures. If the gradient is ambiguous, nothing is changed.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from source_extract.review.retrace import polyline_wt_to_image_pixels

# Neighbours farther than this (image px) are ignored
MAX_NEIGHBOUR_PX = 220.0
# Default °C step when inventing a missing neighbour temperature
DEFAULT_TEMP_STEP_C = 100.0
# Minimum |signed side| proxy (px) to treat a curve as clearly on one side
MIN_SIDE_PX = 4.0


def _poly_midpoint(poly: Sequence[Sequence[float]]) -> tuple[float, float]:
    mid = poly[len(poly) // 2]
    return float(mid[0]), float(mid[1])


def _closest_on_polyline(
    px: float, py: float, poly: Sequence[Sequence[float]]
) -> tuple[float, float, float, float, float]:
    """Return (qx, qy, tx, ty, dist) — closest point + unit tangent of that segment."""
    best_d = float("inf")
    best = (px, py, 1.0, 0.0, best_d)
    if len(poly) == 1:
        qx, qy = float(poly[0][0]), float(poly[0][1])
        return qx, qy, 1.0, 0.0, math.hypot(px - qx, py - qy)
    for i in range(len(poly) - 1):
        ax, ay = float(poly[i][0]), float(poly[i][1])
        bx, by = float(poly[i + 1][0]), float(poly[i + 1][1])
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy
        if len2 < 1e-12:
            t = 0.0
            qx, qy = ax, ay
            tx, ty = 1.0, 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len2))
            qx, qy = ax + t * dx, ay + t * dy
            inv = 1.0 / math.sqrt(len2)
            tx, ty = dx * inv, dy * inv
        d = math.hypot(px - qx, py - qy)
        if d < best_d:
            best_d = d
            best = (qx, qy, tx, ty, d)
    return best


def _signed_side_and_distance(
    poly_a: Sequence[Sequence[float]], poly_b: Sequence[Sequence[float]]
) -> tuple[float, float]:
    """Signed side of B relative to A (+1 / -1) and closest-approach distance (px).

    Side is the sign of the 2-D cross product (tangent_A × (mid_B − closest_on_A)).
    """
    if len(poly_a) < 2 or len(poly_b) < 1:
        return 0.0, float("inf")
    mx, my = _poly_midpoint(poly_b)
    qx, qy, tx, ty, _ = _closest_on_polyline(mx, my, poly_a)
    cross = tx * (my - qy) - ty * (mx - qx)
    # Also sample a few points of B for a more robust distance
    dist = float("inf")
    for j in (0, len(poly_b) // 2, len(poly_b) - 1):
        bx, by = float(poly_b[j][0]), float(poly_b[j][1])
        *_, d = _closest_on_polyline(bx, by, poly_a)
        dist = min(dist, d)
    if abs(cross) < 1e-9:
        return 0.0, dist
    return (1.0 if cross > 0 else -1.0), dist


def _finite_temp(iso: dict[str, Any]) -> float | None:
    t = iso.get("temperature_C")
    if t is None or t == "":
        return None
    try:
        v = float(t)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _estimate_step_c(known: list[tuple[float, float]]) -> float:
    """Median |ΔT| between consecutive known isotherms sorted by signed distance."""
    if len(known) < 2:
        return DEFAULT_TEMP_STEP_C
    known = sorted(known, key=lambda x: x[0])
    gaps = [abs(known[i + 1][1] - known[i][1]) for i in range(len(known) - 1)]
    gaps = [g for g in gaps if g >= 25.0]
    if not gaps:
        return DEFAULT_TEMP_STEP_C
    gaps.sort()
    return float(gaps[len(gaps) // 2])


def _infer_hot_side(
    anchor_t: float,
    others: list[tuple[float, float, float]],
) -> float | None:
    """Return +1 / -1 for the hotter side of the anchor, or None if ambiguous.

    ``others`` entries are ``(side_sign, distance_px, temperature_C)``.
    """
    votes_pos = 0  # + side hotter
    votes_neg = 0
    for side, dist, temp in others:
        if abs(side) < 0.5 or dist < MIN_SIDE_PX:
            continue
        if abs(temp - anchor_t) < 1.0:
            continue
        hotter_on_pos = (temp > anchor_t and side > 0) or (temp < anchor_t and side < 0)
        if hotter_on_pos:
            votes_pos += 1
        else:
            votes_neg += 1
    if votes_pos == 0 and votes_neg == 0:
        return None
    if votes_pos >= votes_neg + 1 and votes_pos >= 1:
        return 1.0
    if votes_neg >= votes_pos + 1 and votes_neg >= 1:
        return -1.0
    return None


def propagate_from_manual_temperature(
    session: dict[str, Any],
    *,
    anchor_index: int,
) -> dict[str, Any]:
    """Correct closest isotherms on each side of a manually set temperature.

    Returns a summary dict stored on the session as ``_lastTemperaturePropagate``.
    Does not push undo / save — caller owns that (runs inside the same undo step).
    """
    from source_extract.review.session_common import _corners_origin

    isos = session["draft"].get("isotherms") or []
    if anchor_index < 0 or anchor_index >= len(isos):
        return {"corrected": [], "reason": "bad-index"}
    anchor_t = _finite_temp(isos[anchor_index])
    if anchor_t is None:
        return {"corrected": [], "reason": "anchor-has-no-temperature"}

    components, corners, origin = _corners_origin(session)
    polys: list[list[list[float]]] = []
    for iso in isos:
        poly = iso.get("polyline_wt") or iso.get("control_wt") or []
        if len(poly) < 2:
            polys.append([])
            continue
        polys.append(
            polyline_wt_to_image_pixels(
                poly, corners=corners, origin=origin, components=components
            )
        )

    anchor_poly = polys[anchor_index]
    if len(anchor_poly) < 2:
        return {"corrected": [], "reason": "anchor-no-geometry"}

    # side_sign, distance, index for every other isotherm
    neighbours: list[tuple[float, float, int]] = []
    known_for_vote: list[tuple[float, float, float]] = []
    known_for_step: list[tuple[float, float]] = [(0.0, anchor_t)]
    for i, poly in enumerate(polys):
        if i == anchor_index or len(poly) < 2:
            continue
        side, dist = _signed_side_and_distance(anchor_poly, poly)
        neighbours.append((side, dist, i))
        t = _finite_temp(isos[i])
        if t is not None and abs(side) >= 0.5:
            known_for_vote.append((side, dist, t))
            # signed distance proxy for step estimation: side * dist
            known_for_step.append((side * dist, t))

    step = _estimate_step_c(known_for_step)

    # Closest on + side and on − side (within reach)
    closest: dict[float, tuple[float, int] | None] = {1.0: None, -1.0: None}
    for side, dist, i in neighbours:
        if abs(side) < 0.5 or dist > MAX_NEIGHBOUR_PX:
            continue
        key = 1.0 if side > 0 else -1.0
        prev = closest[key]
        if prev is None or dist < prev[0]:
            closest[key] = (dist, i)

    # Infer gradient from *other* isotherms — exclude the closest pair we may correct,
    # so inverted neighbours cannot flip the vote against clearer far evidence.
    closest_ids = {hit[1] for hit in closest.values() if hit is not None}
    vote_pool = [
        (side, dist, temp)
        for side, dist, i in neighbours
        if i not in closest_ids
        for temp in [_finite_temp(isos[i])]
        if temp is not None and abs(side) >= 0.5
    ]
    hot_side = _infer_hot_side(anchor_t, vote_pool)
    if hot_side is None:
        # Fall back to all known isotherms if no far evidence exists
        hot_side = _infer_hot_side(anchor_t, known_for_vote)
    if hot_side is None:
        summary = {
            "corrected": [],
            "reason": "ambiguous-gradient",
            "anchorIndex": anchor_index,
            "anchorTemperature_C": anchor_t,
        }
        session["_lastTemperaturePropagate"] = summary
        return summary

    corrected: list[dict[str, Any]] = []
    for side_key, hit in closest.items():
        if hit is None:
            continue
        dist, idx = hit
        iso = isos[idx]
        current = _finite_temp(iso)
        # Hotter side should be above anchor; colder below
        want_hotter = side_key * hot_side > 0
        target = anchor_t + (step if want_hotter else -step)
        if current is not None:
            ok = (current > anchor_t + 0.5) if want_hotter else (current < anchor_t - 0.5)
            if ok:
                continue  # already consistent — keep as is
            # Inconsistent: pull to the correct side of the anchor by one step
            # Prefer keeping magnitude when it already differs enough, only flip side
            if want_hotter and current < anchor_t:
                target = anchor_t + max(step, abs(current - anchor_t))
            elif (not want_hotter) and current > anchor_t:
                target = anchor_t - max(step, abs(current - anchor_t))
            else:
                # Same side of inequality but too close / equal — nudge by step
                target = anchor_t + (step if want_hotter else -step)
        prev = current
        iso["temperature_C"] = float(round(target, 2))
        note = (
            f"temperature aligned to manual {anchor_t:g} °C "
            f"({'hotter' if want_hotter else 'colder'} neighbour, Δ≈{step:g})"
        )
        existing = str(iso.get("notes") or "").strip()
        if "temperature aligned to manual" not in existing:
            iso["notes"] = f"{existing}; {note}".strip("; ").strip()
        corrected.append(
            {
                "index": idx,
                "side": "hotter" if want_hotter else "colder",
                "distancePx": round(dist, 1),
                "from": prev,
                "to": iso["temperature_C"],
            }
        )

    summary = {
        "corrected": corrected,
        "reason": "ok" if corrected else "neighbours-already-consistent",
        "anchorIndex": anchor_index,
        "anchorTemperature_C": anchor_t,
        "hotSide": "positive" if hot_side > 0 else "negative",
        "step_C": step,
    }
    session["_lastTemperaturePropagate"] = summary
    return summary

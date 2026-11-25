"""Helpers for same-temperature isotherm joining."""

from __future__ import annotations

import math
from typing import Any, Sequence

from source_extract.review.retrace import (
    order_image_waypoints_nearest,
    polyline_wt_to_image_pixels,
    polylines_cross,
)

JOIN_GAP_PX = 32.0
CIRCUIT_CLOSE_PX = 28.0

def _temps_equal(a: dict[str, Any], b: dict[str, Any], *, tol_C: float = 0.5) -> bool:
    try:
        ta, tb = a.get("temperature_C"), b.get("temperature_C")
        if ta is None or tb is None or ta == "" or tb == "":
            return False
        fa, fb = float(ta), float(tb)
        if not (fa == fa and fb == fb):
            return False
        return abs(fa - fb) <= tol_C
    except (TypeError, ValueError):
        return False


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _min_polyline_distance(
    a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]
) -> float:
    if not a or not b:
        return float("inf")
    best = float("inf")
    # Endpoint ↔ any vertex (fast) + a few mid samples
    samples_a = [a[0], a[len(a) // 2], a[-1]]
    samples_b = [b[0], b[len(b) // 2], b[-1]]
    for p in samples_a:
        for q in b:
            best = min(best, _dist(p, q))
    for q in samples_b:
        for p in a:
            best = min(best, _dist(p, q))
    # Endpoint-to-endpoint often defines digitization gaps
    for p in (a[0], a[-1]):
        for q in (b[0], b[-1]):
            best = min(best, _dist(p, q))
    return best


def pieces_interact(
    a: Sequence[Sequence[float]], b: Sequence[Sequence[float]], *, gap_px: float = JOIN_GAP_PX
) -> bool:
    """True when polylines cross or come within ``gap_px``."""
    if len(a) < 2 or len(b) < 2:
        return False
    if polylines_cross(a, b):
        return True
    return _min_polyline_distance(a, b) <= gap_px


def _controls_image(
    iso: dict[str, Any],
    *,
    corners: Sequence,
    origin: Sequence[float],
    components: Sequence[str],
) -> list[list[float]]:
    ctrl = iso.get("control_wt") or []
    if len(ctrl) >= 2:
        return polyline_wt_to_image_pixels(
            ctrl, corners=corners, origin=origin, components=components  # type: ignore[arg-type]
        )
    poly = iso.get("polyline_wt") or []
    if len(poly) < 2:
        return []
    pix = polyline_wt_to_image_pixels(
        poly, corners=corners, origin=origin, components=components  # type: ignore[arg-type]
    )
    # Sparse handles from dense poly
    step = max(1, (len(pix) - 1) // 12)
    out = [pix[j] for j in range(0, len(pix), step)]
    if out[-1] != pix[-1]:
        out.append(pix[-1])
    return out


def chain_control_pieces(
    pieces: Sequence[Sequence[Sequence[float]]],
    *,
    gap_px: float = JOIN_GAP_PX,
    circuit_px: float = CIRCUIT_CLOSE_PX,
) -> tuple[list[list[float]], bool]:
    """Chain ordered control pieces end-to-end into one path; detect a circuit.

    Falls back to nearest-neighbour ordering of all points when ends do not meet
    but pieces still interact (e.g. mid-body cross).
    """
    cleaned: list[list[list[float]]] = []
    for piece in pieces:
        pts = [[float(p[0]), float(p[1])] for p in piece if p is not None]
        if len(pts) >= 2:
            cleaned.append(pts)
    if not cleaned:
        return [], False
    if len(cleaned) == 1:
        path = cleaned[0]
        closed = len(path) >= 3 and _dist(path[0], path[-1]) <= circuit_px
        if closed and _dist(path[0], path[-1]) > 1e-6:
            path = path + [path[0][:]]
        return path, closed

    # Start from the longest piece
    start_i = max(range(len(cleaned)), key=lambda i: len(cleaned[i]))
    path = [p[:] for p in cleaned[start_i]]
    used = {start_i}

    def try_attach() -> bool:
        nonlocal path
        best: tuple[float, int, str, bool] | None = None
        for i, piece in enumerate(cleaned):
            if i in used:
                continue
            for reverse in (False, True):
                seq = list(reversed(piece)) if reverse else piece
                d_end = _dist(path[-1], seq[0])
                d_start = _dist(path[0], seq[-1])
                if best is None or d_end < best[0]:
                    best = (d_end, i, "end", reverse)
                if best is None or d_start < best[0]:
                    best = (d_start, i, "start", reverse)
        if best is None or best[0] > gap_px:
            return False
        _d, i, mode, reverse = best
        seq = list(reversed(cleaned[i])) if reverse else list(cleaned[i])
        if mode == "end":
            path.extend(p[:] for p in seq[1:])
        else:
            path = [p[:] for p in seq[:-1]] + path
        used.add(i)
        return True

    while len(used) < len(cleaned):
        if not try_attach():
            break

    # Leftover pieces (e.g. X-cross without near ends) → merge all controls via NN
    if len(used) < len(cleaned):
        all_pts: list[tuple[float, float]] = []
        for piece in cleaned:
            for p in piece:
                all_pts.append((float(p[0]), float(p[1])))
        ordered = order_image_waypoints_nearest(all_pts)
        path = [[float(x), float(y)] for x, y in ordered]
        used = set(range(len(cleaned)))

    # Dedupe consecutive near-duplicates
    deduped: list[list[float]] = [path[0]]
    for p in path[1:]:
        if _dist(deduped[-1], p) > 1.0:
            deduped.append(p)
    path = deduped

    closed = len(path) >= 3 and _dist(path[0], path[-1]) <= circuit_px
    if closed:
        if _dist(path[0], path[-1]) > 1.0:
            path.append(path[0][:])
        elif _dist(path[0], path[-1]) > 1e-9:
            path[-1] = path[0][:]
    return path, closed


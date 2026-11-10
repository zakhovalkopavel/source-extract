"""
source_extract.diagrams.tracing.divider_follower — The stretch of a field divider an isotherm runs along between two track points.
"""
from __future__ import annotations

import math

import numpy as np

from source_extract.diagrams.models.line_scale import LineScale

_STROKE_MEDIAN_PX = 3.0
_CHORD_MIDPOINT_PX = 5.0


def follow_divider(
    start: tuple[float, float],
    end: tuple[float, float],
    stroke: list[tuple[float, float]],
    dividers: list[list[tuple[float, float]]],
    tolerance_px: float = 10.0,
    on_px: float = 5.0,
    scale: LineScale | None = None,
) -> list[tuple[float, float]] | None:
    """The part of a divider polyline from the point nearest ``start`` to the point nearest ``end``, or None.

    Both track points within ``on_px`` of the same divider: the curve between them
    is that divider. Both within ``tolerance_px``: only if the curve runs along it,
    i.e. the median distance of its traced ``stroke`` from that part ≤ 3 px, or,
    without a stroke (hidden or very short step), the chord midpoint within 5 px
    of it. Of several dividers the closest one is used. The returned points start
    and end on the divider (the snapped track points). The 3 px and 5 px are for
    the reference line width, scaled by ``scale``; the two tolerances are taken as given.
    """
    s = scale or LineScale()
    best: tuple[float, list[tuple[float, float]]] | None = None
    for line in dividers:
        if len(line) < 2:
            continue
        points = np.asarray(line, float)
        da, sa, fa = _foot(points, start)
        db, sb, fb = _foot(points, end)
        if da > tolerance_px or db > tolerance_px or abs(sb - sa) < 1e-6:
            continue
        part = _part(points, sa, fa, sb, fb)
        if da <= on_px and db <= on_px:
            pass
        elif stroke:
            if float(np.median([_foot(part, p)[0] for p in stroke])) > s.length(_STROKE_MEDIAN_PX):
                continue
        else:
            middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            if _foot(part, middle)[0] > s.length(_CHORD_MIDPOINT_PX):
                continue
        if best is None or da + db < best[0]:
            best = (da + db, [(float(x), float(y)) for x, y in part])
    return None if best is None else best[1]


def _foot(points: np.ndarray, p) -> tuple[float, float, np.ndarray]:
    """Distance from ``p`` to the polyline, position along it (segment index + fraction), nearest point."""
    a, seg = points[:-1], np.diff(points, axis=0)
    q = np.asarray(p, float)
    u = np.clip(((q - a) * seg).sum(axis=1) / np.maximum((seg ** 2).sum(axis=1), 1e-12), 0.0, 1.0)
    feet = a + u[:, None] * seg
    distance = np.linalg.norm(feet - q, axis=1)
    k = int(distance.argmin())
    return float(distance[k]), k + float(u[k]), feet[k]


def _part(points: np.ndarray, sa: float, fa: np.ndarray, sb: float, fb: np.ndarray) -> np.ndarray:
    if sa <= sb:
        inner = points[math.floor(sa) + 1:math.floor(sb) + 1]
        return np.vstack([fa, inner, fb])
    inner = points[math.floor(sb) + 1:math.floor(sa) + 1][::-1]
    return np.vstack([fa, inner, fb])

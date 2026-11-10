"""
source_extract.diagrams.tracing.curve_tracer — Follow a drawn curve between two pixels (heapq Dijkstra).
"""
from __future__ import annotations

import heapq
import math

import numpy as np

from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.traced_curve import TracedCurve

_COST_INK = 1.0
_COST_OFF = 50.0
_MARGIN_PX = 40
_MAX_RUN = 15
_DIRECTION_STEPS = 5
_NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def trace_path(
    mask: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    waypoints: list[tuple[float, float]] | None = None,
    margin: int | None = None,
    label: str = "",
    scale: LineScale | None = None,
) -> TracedCurve:
    """Shortest 8-connected path, cost 1 on ink and 50 off ink, through the waypoints in order.

    The search is restricted to the bounding box of all points plus ``margin``
    (default 40 px). The returned pixels are moved to the stroke centre (runs
    across up to 15 px, direction over ±5 path pixels); ``gap_px`` is the path
    length crossed off ink. Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    margin = s.count(_MARGIN_PX) if margin is None else margin
    points = [start, *(waypoints or []), end]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0 = max(0, int(min(xs)) - margin)
    y0 = max(0, int(min(ys)) - margin)
    x1 = min(mask.shape[1] - 1, int(max(xs)) + margin)
    y1 = min(mask.shape[0] - 1, int(max(ys)) + margin)
    sub = mask[y0:y1 + 1, x0:x1 + 1]
    cost = np.where(sub, _COST_INK, _COST_OFF)

    path: list[tuple[int, int]] = []
    gap = 0.0
    for a, b in zip(points[:-1], points[1:]):
        start_rc = (int(round(a[1])) - y0, int(round(a[0])) - x0)
        end_rc = (int(round(b[1])) - y0, int(round(b[0])) - x0)
        segment = _dijkstra(cost, start_rc, end_rc)
        if path:
            segment = segment[1:]
        path.extend(segment)
    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        if not sub[r1, c1]:
            gap += math.hypot(r1 - r0, c1 - c0)
    page_path = [(c + x0, r + y0) for r, c in path]
    centred = _centre(mask, page_path, s.count(_MAX_RUN), s.count(_DIRECTION_STEPS))
    return TracedCurve(pixels=centred, gap_px=gap, label=label)


def _dijkstra(cost: np.ndarray, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    rows, cols = cost.shape
    for r, c in (start, end):
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError("trace endpoint outside the search box")
    dist = np.full(cost.shape, np.inf)
    previous = np.full(cost.shape, -1, dtype=np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    end_r, end_c = end
    while heap:
        d, r, c = heapq.heappop(heap)
        if d > dist[r, c]:
            continue
        if r == end_r and c == end_c:
            break
        for dr, dc in _NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                step = cost[nr, nc] * (1.4142135623730951 if dr and dc else 1.0)
                nd = d + step
                if nd < dist[nr, nc]:
                    dist[nr, nc] = nd
                    previous[nr, nc] = r * cols + c
                    heapq.heappush(heap, (nd, nr, nc))
    if not np.isfinite(dist[end]):
        raise ValueError("no path found")
    path = [end]
    index = previous[end]
    while index >= 0:
        r, c = divmod(int(index), cols)
        path.append((r, c))
        if (r, c) == start:
            break
        index = previous[r, c]
    return path[::-1]


def _centre(mask: np.ndarray, path: list[tuple[int, int]], max_run: int, steps: int) -> list[tuple[float, float]]:
    """Move each path pixel to the centre of its stroke across the local direction."""
    out: list[tuple[float, float]] = []
    n = len(path)
    for i, (x, y) in enumerate(path):
        xa, ya = path[max(0, i - steps)]
        xb, yb = path[min(n - 1, i + steps)]
        if not mask[y, x]:
            out.append((float(x), float(y)))
            continue
        if abs(xb - xa) >= abs(yb - ya):
            top, bottom = _extent(mask[:, x], y, max_run)
            if bottom - top + 1 <= max_run:
                out.append((float(x), (top + bottom) / 2.0))
                continue
        else:
            left, right = _extent(mask[y, :], x, max_run)
            if right - left + 1 <= max_run:
                out.append(((left + right) / 2.0, float(y)))
                continue
        out.append((float(x), float(y)))
    return out


def _extent(line: np.ndarray, index: int, max_run: int) -> tuple[int, int]:
    low = index
    while low - 1 >= 0 and line[low - 1] and index - low < max_run:
        low -= 1
    high = index
    while high + 1 < len(line) and line[high + 1] and high - index < max_run:
        high += 1
    return low, high

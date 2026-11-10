"""
source_extract.diagrams.tracing.polyline_simplifier — Douglas–Peucker simplification in wt% space.
"""
from __future__ import annotations

import numpy as np


def simplify_polyline(points: list[list[float]], tolerance: float = 0.1) -> list[list[float]]:
    """Keep the first and last point and every point farther than ``tolerance`` from the simplified line."""
    if len(points) <= 2:
        return [list(p) for p in points]
    data = np.array(points, float)
    keep = np.zeros(len(data), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(data) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        a, b = data[first], data[last]
        segment = b - a
        length = float(np.linalg.norm(segment))
        between = data[first + 1:last]
        if length == 0:
            distances = np.linalg.norm(between - a, axis=1)
        else:
            t = np.clip(((between - a) @ segment) / (length * length), 0.0, 1.0)
            distances = np.linalg.norm(between - (a + t[:, None] * segment), axis=1)
        index = int(np.argmax(distances))
        if distances[index] > tolerance:
            split = first + 1 + index
            keep[split] = True
            stack.append((first, split))
            stack.append((split, last))
    return [list(points[i]) for i in np.flatnonzero(keep)]

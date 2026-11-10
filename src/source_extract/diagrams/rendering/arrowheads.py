"""
source_extract.diagrams.rendering.arrowheads — Triangles marking a stored boundary arrow along a polyline.
"""
from __future__ import annotations

import numpy as np

_PLACES = {">": ((0.5, 1),), "<": ((0.5, -1),), "<>": ((0.25, -1), (0.75, 1))}


def arrowheads(points: list[tuple[float, float]] | np.ndarray, arrow: str, size: float, half: float,
               span: float) -> list[list[tuple[float, float]]]:
    """Triangles (tip first) for ``arrow`` on the polyline ``points`` (drawing pixels, path order).

    ``>`` one head at the middle pointing along the polyline, ``<`` against it, ``<>`` two heads
    at a quarter and three quarters pointing away from the middle; ``?`` or an unknown value none.
    ``size`` is the head length, ``half`` its half width, ``span`` the arc length either side
    of the head used for its direction.
    """
    xy = np.asarray(points, float)
    if len(xy) < 2 or arrow not in _PLACES:
        return []
    length = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))])
    if length[-1] <= 0:
        return []

    def at(s: float) -> np.ndarray:
        return np.array([np.interp(s, length, xy[:, i]) for i in (0, 1)])

    heads = []
    for fraction, sense in _PLACES[arrow]:
        centre_s = fraction * length[-1]
        direction = (at(centre_s + span) - at(centre_s - span)) * sense
        norm = np.linalg.norm(direction)
        direction = direction / norm if norm > 1e-9 else np.array([1.0, 0.0])
        normal = np.array([-direction[1], direction[0]])
        centre = at(centre_s)
        tip, base = centre + direction * size / 2, centre - direction * size / 2
        heads.append([tuple(tip), tuple(base + normal * half), tuple(base - normal * half)])
    return heads

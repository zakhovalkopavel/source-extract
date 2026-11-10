"""
source_extract.diagrams.tracing.curve_sampler — Sample a traced binary curve on a wt% grid.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.curve_sample import CurveSample

_ENDPOINT_EPS = 0.05
_LABEL_DRAWING_LIMIT = 0.5


def sample_curve(
    traced: list[tuple[float, float]],
    grid: list[float],
    start: tuple[float, float],
    end: tuple[float, float],
    start_drawn: float | None = None,
    end_drawn: float | None = None,
    junction_tolerance: float = 1.5,
) -> CurveSample:
    """Interpolate ``traced`` (wt%, °C) at the grid values strictly between ``start`` and ``end``.

    ``start`` / ``end`` are the printed values and become the first and last
    points. When a drawn junction composition differs from its label by more
    than 0.5 wt%, grid values within ``junction_tolerance`` of the label are
    dropped. Temperatures are rounded to 1 °C.
    """
    low, high = sorted((start[0], end[0]))
    interior = [g for g in grid if low + _ENDPOINT_EPS < g < high - _ENDPOINT_EPS]
    dropped: list[float] = []
    for label, drawn in ((start[0], start_drawn), (end[0], end_drawn)):
        if drawn is None or abs(drawn - label) <= _LABEL_DRAWING_LIMIT:
            continue
        for g in interior:
            if abs(g - label) <= junction_tolerance + 1e-9 and g not in dropped:
                dropped.append(g)
    interior = [g for g in interior if g not in dropped]

    uncovered: list[float] = []
    samples: list[list[float]] = []
    if traced and interior:
        xs, ys = _monotone(traced)
        for g in interior:
            if g < xs[0] - 1e-9 or g > xs[-1] + 1e-9:
                uncovered.append(g)
                continue
            samples.append([g, int(round(float(np.interp(g, xs, ys))))])
    else:
        uncovered = list(interior)

    first = [start[0], _temperature(start[1])]
    last = [end[0], _temperature(end[1])]
    points = [first, *samples, last]
    points.sort(key=lambda p: p[0])
    return CurveSample(points=points, dropped=sorted(dropped), uncovered=uncovered)


def _monotone(traced: list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    data = np.array(sorted(traced), float)
    keys = np.round(data[:, 0], 4)
    unique, inverse = np.unique(keys, return_inverse=True)
    means = np.bincount(inverse, weights=data[:, 1]) / np.bincount(inverse)
    return unique, means


def _temperature(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value

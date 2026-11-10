"""
source_extract.diagrams.tracing.quadratic_segment_fitter — One quadratic Bézier arc between two track points, fitted to the traced stroke.
"""
from __future__ import annotations

import math

import numpy as np

from source_extract.diagrams.models.line_scale import LineScale

_ITERATIONS = 6
_OUTLIER_PX = 4.0
_OUTLIER_FACTOR = 2.5
_DENSE = 200
_STEP_PX = 3.0


def fit_quadratic_segment(
    pixels: list[tuple[float, float]],
    start: tuple[float, float],
    end: tuple[float, float],
    step_px: float | None = None,
    scale: LineScale | None = None,
) -> list[tuple[float, float]]:
    """Points every ``step_px`` along the quadratic Bézier from ``start`` to ``end`` that best fits ``pixels``.

    The ends are fixed; only the control point is fitted (least squares, foot-point
    parameters, samples further than max(4 px, 2.5 × median residual) dropped, so a
    label lying on the stroke does not bend the arc). The control point is kept
    within the chord's extent along the chord, so the arc has no inflection and
    no turning back: it is at most as curved as one parabola between the points.
    ``step_px`` defaults to 3 px; pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    step_px = s.length(_STEP_PX) if step_px is None else step_px
    p0, p2 = np.asarray(start, float), np.asarray(end, float)
    chord = p2 - p0
    length = float(np.linalg.norm(chord))
    if length < 1e-9:
        return [tuple(map(float, p0)), tuple(map(float, p2))]
    control = (p0 + p2) / 2.0
    samples = np.asarray(pixels, float)
    if len(samples) >= 3:
        t = np.clip((samples - p0) @ chord / length ** 2, 0.0, 1.0)
        keep = np.ones(len(samples), bool)
        dense_t = np.linspace(0.0, 1.0, _DENSE)
        for _ in range(_ITERATIONS):
            control = _clamped(_control(samples[keep], t[keep], p0, p2), p0, chord / length, length)
            dense = _bezier(p0, control, p2, dense_t)
            distances = np.linalg.norm(samples[:, None, :] - dense[None, :, :], axis=2)
            nearest = distances.argmin(axis=1)
            t = dense_t[nearest]
            residual = distances[np.arange(len(samples)), nearest]
            keep = residual <= max(s.length(_OUTLIER_PX), _OUTLIER_FACTOR * float(np.median(residual)))
            if keep.sum() < 3:
                keep = residual <= np.quantile(residual, 0.5)
    rough = _bezier(p0, control, p2, np.linspace(0.0, 1.0, _DENSE))
    curve_length = float(np.linalg.norm(np.diff(rough, axis=0), axis=1).sum())
    count = max(2, math.ceil(curve_length / step_px) + 1)
    points = _bezier(p0, control, p2, np.linspace(0.0, 1.0, count))
    return [(float(x), float(y)) for x, y in points]


def _control(samples: np.ndarray, t: np.ndarray, p0: np.ndarray, p2: np.ndarray) -> np.ndarray:
    weight = 2.0 * t * (1.0 - t)
    base = ((1.0 - t) ** 2)[:, None] * p0 + (t ** 2)[:, None] * p2
    denominator = float((weight ** 2).sum())
    if denominator < 1e-12:
        return (p0 + p2) / 2.0
    return (weight[:, None] * (samples - base)).sum(axis=0) / denominator


def _clamped(control: np.ndarray, p0: np.ndarray, direction: np.ndarray, length: float) -> np.ndarray:
    offset = control - p0
    along = float(offset @ direction)
    across = offset - along * direction
    return p0 + min(max(along, 0.0), length) * direction + across


def _bezier(p0: np.ndarray, control: np.ndarray, p2: np.ndarray, t: np.ndarray) -> np.ndarray:
    t = t[:, None]
    return (1.0 - t) ** 2 * p0 + 2.0 * t * (1.0 - t) * control + t ** 2 * p2

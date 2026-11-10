"""
source_extract.diagrams.tracing.convex_curve_fitter — One Bézier curve of degree ≤ 4 without inflection through the track points of an isotherm inside one field.
"""
from __future__ import annotations

import math

import numpy as np

from source_extract.diagrams.models.line_scale import LineScale

_DEGREES = (2, 3, 4)
_POINT_WEIGHT = 1000.0
_POINT_TOLERANCE_PX = 2.5
_STROKE_TOLERANCE_PX = 2.0
_STROKE_QUANTILE = 0.75
_PRIOR_WEIGHT = 1e-3
_ITERATIONS = 6
_OUTLIER_PX = 4.0
_OUTLIER_FACTOR = 2.5
_DENSE = 400
_FLAT_CURVATURE = 1e-4
_BACKTRACK_PX = 0.5
_STEP_PX = 3.0


def fit_convex_curve(
    pixels: list[tuple[float, float]],
    points: list[tuple[float, float]],
    step_px: float | None = None,
    scale: LineScale | None = None,
) -> tuple[list[tuple[float, float]], int, float]:
    """Points every ``step_px`` along one Bézier curve from ``points[0]`` to ``points[-1]`` near the inner ``points``.

    The ends are fixed. The inner track points pull strongly and the stroke
    ``pixels`` (labels and stray strokes dropped as outliers) fill in the shape.
    Degrees 2, 3 and 4 are tried in turn; a curve with an inflection, or one
    that turns back along the chord, is rejected. The lowest degree passing
    within 2.5 px of every inner point, with three quarters of the stroke within
    2 px, is kept; else the valid one coming closest. Returns (curve points, degree, largest distance of an inner point
    from the curve). Equal ends give a closed loop. ``step_px`` defaults to 3 px; pixel
    sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    step_px = s.length(_STEP_PX) if step_px is None else step_px
    track = np.asarray(points, float)
    samples = np.asarray(pixels, float).reshape(-1, 2)
    best: tuple[np.ndarray, int, float, float] | None = None
    for degree in _DEGREES:
        control = _fit(degree, track, samples, s.length(_OUTLIER_PX))
        dense = _bezier(control, np.linspace(0.0, 1.0, _DENSE))
        if degree > 2 and not (_convex(dense, _FLAT_CURVATURE / s.factor)
                               and _forward(dense, track[0], track[-1], s.length(_BACKTRACK_PX))):
            continue
        offset = _offset(track[1:-1], dense)
        stroke = float(np.quantile(_nearest(samples, dense)[1], _STROKE_QUANTILE)) if len(samples) else 0.0
        score = max(offset / s.length(_POINT_TOLERANCE_PX), stroke / s.length(_STROKE_TOLERANCE_PX))
        if best is None or score < best[3] - 1e-9:
            best = (control, degree, offset, score)
        if score <= 1.0:
            break
    control, degree, offset, _ = best
    rough = _bezier(control, np.linspace(0.0, 1.0, _DENSE))
    length = float(np.linalg.norm(np.diff(rough, axis=0), axis=1).sum())
    count = max(2, math.ceil(length / step_px) + 1)
    curve = _bezier(control, np.linspace(0.0, 1.0, count))
    curve[0], curve[-1] = track[0], track[-1]
    return [(float(x), float(y)) for x, y in curve], degree, offset


def _fit(degree: int, track: np.ndarray, samples: np.ndarray, outlier_px: float) -> np.ndarray:
    p0, pn = track[0], track[-1]
    inner = track[1:-1]
    t_inner = _track_parameter(inner, track)
    t_samples = _track_parameter(samples, track)
    keep = np.ones(len(samples), bool)
    dense_t = np.linspace(0.0, 1.0, _DENSE)
    control = _line_control(degree, p0, pn)
    for _ in range(_ITERATIONS):
        control = _solve(degree, p0, pn, inner, t_inner, samples[keep], t_samples[keep])
        if degree == 2:
            control[1] = _clamped(control[1], p0, pn)
        dense = _bezier(control, dense_t)
        if len(inner):
            t_inner = dense_t[_nearest(inner, dense)[0]]
        if len(samples):
            nearest, residual = _nearest(samples, dense)
            t_samples = dense_t[nearest]
            keep = residual <= max(outlier_px, _OUTLIER_FACTOR * float(np.median(residual)))
    return control


def _solve(degree, p0, pn, inner, t_inner, samples, t_samples) -> np.ndarray:
    data = np.concatenate([inner, samples]) if len(samples) else inner
    t = np.concatenate([t_inner, t_samples]) if len(samples) else t_inner
    weight = np.concatenate([np.full(len(inner), _POINT_WEIGHT), np.ones(len(samples))])
    basis = _bernstein(degree, t)
    target = data - basis[:, :1] * p0 - basis[:, -1:] * pn
    prior = _line_control(degree, p0, pn)[1:-1]
    rows = np.concatenate([basis[:, 1:-1] * np.sqrt(weight)[:, None], np.eye(degree - 1) * math.sqrt(_PRIOR_WEIGHT)])
    rhs = np.concatenate([target * np.sqrt(weight)[:, None], prior * math.sqrt(_PRIOR_WEIGHT)])
    inner_control, *_ = np.linalg.lstsq(rows, rhs, rcond=None)
    return np.vstack([p0, inner_control, pn])


def _line_control(degree: int, p0: np.ndarray, pn: np.ndarray) -> np.ndarray:
    return np.array([p0 + (pn - p0) * i / degree for i in range(degree + 1)])


def _bernstein(degree: int, t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, float)[:, None]
    i = np.arange(degree + 1)[None, :]
    binomial = np.array([math.comb(degree, k) for k in range(degree + 1)])[None, :]
    return binomial * t ** i * (1.0 - t) ** (degree - i)


def _bezier(control: np.ndarray, t: np.ndarray) -> np.ndarray:
    return _bernstein(len(control) - 1, t) @ control


def _track_parameter(samples: np.ndarray, track: np.ndarray) -> np.ndarray:
    """Position of each sample along the track polyline, 0 at the start, 1 at the end."""
    if len(samples) == 0:
        return np.zeros(0)
    a, b = track[:-1], track[1:]
    seg = b - a
    seg_length = np.linalg.norm(seg, axis=1)
    total = float(seg_length.sum())
    if total < 1e-9:
        return np.linspace(0.0, 1.0, len(samples))
    start = np.concatenate([[0.0], np.cumsum(seg_length)[:-1]])
    rel = samples[:, None, :] - a[None, :, :]
    u = np.clip((rel * seg[None]).sum(axis=2) / np.maximum(seg_length ** 2, 1e-12)[None], 0.0, 1.0)
    foot = a[None] + u[..., None] * seg[None]
    distance = np.linalg.norm(samples[:, None, :] - foot, axis=2)
    k = distance.argmin(axis=1)
    rows = np.arange(len(samples))
    return (start[k] + u[rows, k] * seg_length[k]) / total


def _nearest(samples: np.ndarray, dense: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    distances = np.linalg.norm(samples[:, None, :] - dense[None, :, :], axis=2)
    nearest = distances.argmin(axis=1)
    return nearest, distances[np.arange(len(samples)), nearest]


def _clamped(control: np.ndarray, p0: np.ndarray, pn: np.ndarray) -> np.ndarray:
    chord = pn - p0
    length = float(np.linalg.norm(chord))
    if length < 1e-9:
        return control
    direction = chord / length
    offset = control - p0
    along = float(offset @ direction)
    return p0 + min(max(along, 0.0), length) * direction + (offset - along * direction)


def _convex(dense: np.ndarray, flat: float) -> bool:
    d1 = np.gradient(dense, axis=0)
    d2 = np.gradient(d1, axis=0)
    speed = np.maximum(np.linalg.norm(d1, axis=1), 1e-12)
    curvature = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / speed ** 3
    curvature = curvature[2:-2]
    return not ((curvature > flat).any() and (curvature < -flat).any())


def _forward(dense: np.ndarray, p0: np.ndarray, pn: np.ndarray, backtrack_px: float) -> bool:
    chord = pn - p0
    length = float(np.linalg.norm(chord))
    if length < 1.0:
        return True
    along = (dense - p0) @ (chord / length)
    return bool((np.maximum.accumulate(along) - along).max() <= backtrack_px)


def _offset(inner: np.ndarray, dense: np.ndarray) -> float:
    if len(inner) == 0:
        return 0.0
    return float(_nearest(inner, dense)[1].max())

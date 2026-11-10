"""
source_extract.diagrams.tracing.contour_segments — Line segments of one level of a sampled surface (marching squares).
"""
from __future__ import annotations

import numpy as np


def contour_segments(
    grid: np.ndarray, level: float, origin: tuple[float, float], step: float,
) -> list[tuple[float, float, float, float]]:
    """Segments ``(x0, y0, x1, y1)`` where ``grid`` crosses ``level``.

    ``grid[i, j]`` is the value at ``(origin[0] + j·step, origin[1] + i·step)``; cells with
    a NaN corner are skipped. Crossings on the cell edges are linearly interpolated; a cell
    with four crossings (saddle) joins them by the cell-centre value.
    """
    values = grid - level
    above = values > 0
    a, b = values[:-1, :-1], values[:-1, 1:]
    c, d = values[1:, 1:], values[1:, :-1]
    valid = np.isfinite(a) & np.isfinite(b) & np.isfinite(c) & np.isfinite(d)
    corners = (above[:-1, :-1].astype(int) + above[:-1, 1:] * 2 + above[1:, 1:] * 4 + above[1:, :-1] * 8)
    rows, cols = np.nonzero(valid & (corners != 0) & (corners != 15))
    out = []
    for i, j in zip(rows.tolist(), cols.tolist()):
        va, vb, vc, vd = values[i, j], values[i, j + 1], values[i + 1, j + 1], values[i + 1, j]
        crossings = []
        for (p, vp), (q, vq) in (((0, va), (1, vb)), ((1, vb), (2, vc)), ((2, vc), (3, vd)), ((3, vd), (0, va))):
            if (vp > 0) != (vq > 0):
                t = vp / (vp - vq)
                crossings.append(_along(p, q, t))
        if len(crossings) == 4 and ((va + vb + vc + vd) > 0) != (va > 0):
            crossings = [crossings[3], crossings[0], crossings[1], crossings[2]]
        for k in range(0, len(crossings) - 1, 2):
            (u0, w0), (u1, w1) = crossings[k], crossings[k + 1]
            out.append((origin[0] + (j + u0) * step, origin[1] + (i + w0) * step,
                        origin[0] + (j + u1) * step, origin[1] + (i + w1) * step))
    return out


_CORNER = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _along(p: int, q: int, t: float) -> tuple[float, float]:
    (x0, y0), (x1, y1) = _CORNER[p], _CORNER[q]
    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

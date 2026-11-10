"""
source_extract.diagrams.detection.junction_locator — Snap a seed pixel to where a curve meets an invariant line.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

_BOX = 30
_ROWS = 14
_STEEP_RUN = 12
_WALK_JUMP = 3.0


def locate_junction(
    mask: np.ndarray,
    seed: tuple[float, float],
    line_row: Callable[[float], float],
    line_thickness: float,
    box: int = _BOX,
) -> tuple[float, float]:
    """Page pixel where the curve arriving from above meets the line.

    ``line_row(x)`` is the line centre row at column x. Rows just above the
    line are scanned inside ``box`` px of the seed; the curve centre is followed
    from the run nearest the seed and extrapolated to the line centre. For a
    curve meeting the line at a shallow angle (long runs) the curve is fitted
    column by column instead.
    """
    sx, sy = seed
    x0, x1 = int(round(sx - box)), int(round(sx + box))
    half = line_thickness / 2.0
    centres: list[tuple[float, float]] = []
    run_lengths: list[int] = []
    previous = sx
    for k in range(3, 3 + _ROWS):
        row = int(round(line_row(sx) - half - k))
        runs = _runs(mask[row, x0:x1 + 1])
        if not runs:
            break
        centre_list = [(x0 + (a + b) / 2.0, b - a + 1) for a, b in runs]
        centre, length = min(centre_list, key=lambda c: abs(c[0] - previous))
        if centres and abs(centre - previous) > 8:
            break
        centres.append((centre, float(row)))
        run_lengths.append(length)
        previous = centre
    if len(centres) >= 3 and float(np.median(run_lengths)) <= _STEEP_RUN:
        xs = np.array([c[0] for c in centres])
        ys = np.array([c[1] for c in centres])
        slope, offset = np.polyfit(ys, xs, 1)
        x = float(offset + slope * line_row(sx))
        if abs(x - sx) <= box:
            return x, line_row(x)
    shallow = _shallow_junction(mask, sx, sy, line_row, half, box)
    if shallow is not None:
        return shallow, line_row(shallow)
    if centres:
        x = centres[0][0]
        return x, line_row(x)
    return sx, line_row(sx)


def _shallow_junction(mask, sx, sy, line_row, half, box) -> float | None:
    """Follow the curve through the seed column by column (both directions) and extend it to the line.

    The walk stops where the curve merges with the line or jumps by more than
    3 px, so the other branch of a V is not mixed in.
    """

    def centres_at(x: int) -> list[float]:
        top = int(round(line_row(x)))
        while top - 1 >= 0 and mask[top - 1, x] and line_row(x) - top < half + 3:
            top -= 1
        column = mask[top - 25:top, x]
        return [top - 25 + (a + b) / 2.0 for a, b in _runs(column) if b != len(column) - 1]

    def centre_near(x: int, previous: float) -> float | None:
        centres = centres_at(x)
        if not centres:
            return None
        nearest = min(centres, key=lambda c: abs(c - previous))
        return nearest if abs(nearest - previous) <= _WALK_JUMP else None

    # start at the curve pixel nearest the seed that is clear of the line
    candidates = [
        (x, c) for x in range(int(round(sx - box)), int(round(sx + box)) + 1) for c in centres_at(x)
    ]
    if not candidates:
        return None
    start_x, start = min(candidates, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)
    points = [(float(start_x), start)]
    for step in (1, -1):
        previous = start
        for x in range(start_x + step, start_x + step * (box + 1), step):
            centre = centre_near(x, previous)
            if centre is None:
                break
            points.append((float(x), centre))
            previous = centre
    if len(points) < 5:
        return None
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    order = np.argsort(np.abs(xs - sx))[:15]
    slope, offset = np.polyfit(xs[order], ys[order], 1)
    if abs(slope) < 0.05:
        return None
    target = line_row(sx)
    x = float((target - offset) / slope)
    return x if abs(x - sx) <= box else None


def _runs(values: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate([[0], values.astype(np.int8), [0]])
    diff = np.diff(padded)
    return list(zip(np.flatnonzero(diff == 1), np.flatnonzero(diff == -1) - 1))

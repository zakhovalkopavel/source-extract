"""
source_extract.diagrams.detection.horizontal_line_detector — Horizontal invariant lines inside the frame.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.binary_calibration import BinaryCalibration
from source_extract.diagrams.models.frame import Frame
from source_extract.diagrams.models.measured_line import MeasuredLine

_GAP = 2
_COLLINEAR_PX = 4.0


def detect_horizontal_lines(
    mask: np.ndarray,
    frame: Frame,
    calibration: BinaryCalibration,
    min_run: int = 80,
) -> list[MeasuredLine]:
    """Rows (rotation removed) holding an ink run ≥ ``min_run`` px; consecutive rows merged."""
    margin = int(np.ceil(frame.line_width)) + 3
    corners = frame.corners()
    x0 = int(np.ceil(max(corners["topLeft"][0], corners["bottomLeft"][0]))) + margin
    x1 = int(np.floor(min(corners["topRight"][0], corners["bottomRight"][0]))) - margin
    y0 = int(np.ceil(max(corners["topLeft"][1], corners["topRight"][1]))) + margin
    y1 = int(np.floor(min(corners["bottomLeft"][1], corners["bottomRight"][1]))) - margin
    xs = np.arange(x0, x1 + 1)
    shift = np.round(calibration.bottom_slope * (xs - calibration.ref_px)).astype(int)
    rows = np.arange(y0, y1 + 1)
    index_rows = np.clip(rows[:, None] + shift[None, :], 0, mask.shape[0] - 1)
    deskewed = mask[index_rows, xs[None, :]]

    groups: list[list[tuple[int, int, int]]] = []
    for r, row in enumerate(deskewed):
        for start, end in _long_runs(row, min_run):
            item = (int(rows[r]), int(xs[start]), int(xs[end]))
            group = next((g for g in groups if g[-1][0] == item[0] - 1 and _overlap(item, g[-1])), None)
            if group is None:
                groups.append([item])
            else:
                group.append(item)

    pieces = [
        (
            (group[0][0] + group[-1][0]) / 2.0,
            float(group[0][0]),
            float(group[-1][0]),
            float(np.median([g[1] for g in group])),
            float(np.median([g[2] for g in group])),
        )
        for group in groups
    ]
    lines: list[MeasuredLine] = []
    for level, top, bottom, x_start, x_end in _merge_collinear(pieces):
        _, temperature = calibration.to_data(calibration.ref_px, level)
        lines.append(MeasuredLine(level, top, bottom, x_start, x_end, temperature))
    return sorted(lines, key=lambda line: line.y_level)


def _merge_collinear(pieces):
    """Join pieces of one line broken by a label or a crossing: levels within 4 px, extents not overlapping.

    The merged level is the length-weighted mean; the rows are those of the longest piece.
    """
    pieces = sorted(pieces, key=lambda p: p[0])
    merged: list[list[tuple]] = []
    for piece in pieces:
        target = next(
            (
                group for group in merged
                if abs(_weighted_level(group) - piece[0]) <= _COLLINEAR_PX
                and not any(_overlap((0, piece[3], piece[4]), (0, g[3], g[4])) for g in group)
            ),
            None,
        )
        if target is None:
            merged.append([piece])
        else:
            target.append(piece)
    out = []
    for group in merged:
        longest = max(group, key=lambda g: g[4] - g[3])
        out.append((_weighted_level(group), longest[1], longest[2], min(g[3] for g in group), max(g[4] for g in group)))
    return out


def _weighted_level(group) -> float:
    weights = [g[4] - g[3] + 1 for g in group]
    return float(np.average([g[0] for g in group], weights=weights))


def _overlap(a, b) -> bool:
    return a[1] <= b[2] and b[1] <= a[2]


def _long_runs(row: np.ndarray, min_run: int) -> list[tuple[int, int]]:
    ink = np.flatnonzero(row)
    if len(ink) == 0:
        return []
    breaks = np.flatnonzero(np.diff(ink) > _GAP + 1)
    starts = np.concatenate([[ink[0]], ink[breaks + 1]])
    ends = np.concatenate([ink[breaks], [ink[-1]]])
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s + 1 >= min_run]

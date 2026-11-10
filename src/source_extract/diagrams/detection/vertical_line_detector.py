"""
source_extract.diagrams.detection.vertical_line_detector — Vertical strokes (compound lines) inside the frame.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.binary_calibration import BinaryCalibration
from source_extract.diagrams.models.frame import Frame

_GAP = 2


def detect_vertical_lines(
    mask: np.ndarray,
    frame: Frame,
    calibration: BinaryCalibration,
    min_run: int = 120,
) -> list[tuple[float, float, float]]:
    """``(x_level, y_top, y_bottom)`` of columns (left-frame tilt removed) with an ink run ≥ ``min_run`` px."""
    margin = int(np.ceil(frame.line_width)) + 3
    corners = frame.corners()
    x0 = int(np.ceil(max(corners["topLeft"][0], corners["bottomLeft"][0]))) + margin
    x1 = int(np.floor(min(corners["topRight"][0], corners["bottomRight"][0]))) - margin
    y0 = int(np.ceil(max(corners["topLeft"][1], corners["topRight"][1]))) + margin
    y1 = int(np.floor(min(corners["bottomLeft"][1], corners["bottomRight"][1]))) - margin
    ys = np.arange(y0, y1 + 1)
    shift = np.round(calibration.left_slope * (ys - calibration.ref_py)).astype(int)
    cols = np.arange(x0, x1 + 1)
    index_cols = np.clip(cols[None, :] + shift[:, None], 0, mask.shape[1] - 1)
    deskewed = mask[ys[:, None], index_cols]

    hits: list[tuple[int, int, int]] = []
    for c in range(deskewed.shape[1]):
        ink = np.flatnonzero(deskewed[:, c])
        if len(ink) < min_run:
            continue
        breaks = np.flatnonzero(np.diff(ink) > _GAP + 1)
        starts = np.concatenate([[ink[0]], ink[breaks + 1]])
        ends = np.concatenate([ink[breaks], [ink[-1]]])
        longest = int(np.argmax(ends - starts))
        if ends[longest] - starts[longest] + 1 >= min_run:
            hits.append((int(cols[c]), int(ys[starts[longest]]), int(ys[ends[longest]])))

    lines: list[tuple[float, float, float]] = []
    group: list[tuple[int, int, int]] = []
    for hit in hits + [None]:
        if hit is not None and group and hit[0] == group[-1][0] + 1:
            group.append(hit)
            continue
        if group and len(group) <= 12:
            lines.append(
                (
                    float(np.mean([g[0] for g in group])),
                    float(min(g[1] for g in group)),
                    float(max(g[2] for g in group)),
                )
            )
        group = [hit] if hit is not None else []
    return lines

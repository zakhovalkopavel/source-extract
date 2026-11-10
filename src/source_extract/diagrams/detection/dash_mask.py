"""
source_extract.diagrams.detection.dash_mask — Keep only the dashes of an ink mask (short, thin, elongated components).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from source_extract.diagrams.models.line_scale import LineScale

_SIZE_PX = (8, 60)
_MIN_ELONGATION = 1.5
_MAX_MEAN_WIDTH_PX = 12.0


def dash_mask(mask: np.ndarray, size_px: tuple[int, int] | None = None, scale: LineScale | None = None) -> np.ndarray:
    """Pixels of the components whose largest box side lies in ``size_px`` (min inclusive, max exclusive;
    default 8–60 px), with axis ratio ≥ 1.5 and mean width (area / length along the axis) ≤ 12 px (bold dashes).

    Solid lines, the frame and anything touching them are dropped, so a trace on
    this mask can only follow dashes (or cross empty paper at the gap cost).
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    size_px = size_px or (s.count(_SIZE_PX[0]), s.count(_SIZE_PX[1]))
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3), bool))
    keep = np.zeros(labels.max() + 1, bool)
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None or not size_px[0] <= max(box[0].stop - box[0].start, box[1].stop - box[1].start) < size_px[1]:
            continue
        ys, xs = np.nonzero(labels[box] == index)
        points = np.column_stack([xs, ys]).astype(float)
        centre = points.mean(axis=0)
        values, vectors = np.linalg.eigh(np.cov((points - centre).T))
        along = (points - centre) @ vectors[:, 1]
        if values[1] < _MIN_ELONGATION ** 2 * max(values[0], 1e-9):
            continue
        keep[index] = len(points) / max(along.max() - along.min(), 1.0) <= s.length(_MAX_MEAN_WIDTH_PX)
    return keep[labels]

"""
source_extract.diagrams.detection.stroke_width_filter — Keep strokes whose width lies in a range.

Stroke width = 2 × distance transform on the stroke ridge. Text, thin arrows
and dashes fall outside the range of the drawn curves and drop out.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def stroke_width_filter(mask: np.ndarray, width_range: tuple[float, float]) -> np.ndarray:
    low, high = width_range
    distance = ndimage.distance_transform_edt(mask)
    ridge = mask & (distance >= ndimage.maximum_filter(distance, size=3))
    width = 2.0 * distance
    keep_ridge = ridge & (width >= low) & (width <= high)
    radius = int(np.ceil(high / 2.0)) + 1
    grown = ndimage.binary_dilation(keep_ridge, structure=np.ones((3, 3), bool), iterations=radius)
    return mask & grown

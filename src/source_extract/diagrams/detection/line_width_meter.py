"""
source_extract.diagrams.detection.line_width_meter — Typical width of the drawn lines of a page (its pixel scale).
"""
from __future__ import annotations

import cv2
import numpy as np

from source_extract.diagrams.models.line_scale import LineScale


def measure_line_scale(mask: np.ndarray) -> LineScale:
    """Mean stroke width of ``mask``: 2 × ink area / outline length.

    A stroke of width w and length L has area w·L and an outline of about 2·L,
    so the ratio is the length-weighted mean width of all lines, dashes and
    letters; it follows the render resolution and the line weight of the source.
    A mask without ink gives the reference scale.
    """
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outline = sum(cv2.arcLength(c, True) for c in contours)
    if outline <= 0:
        return LineScale()
    return LineScale(round(2.0 * float(mask.sum()) / outline, 2), "measured")

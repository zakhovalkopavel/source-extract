"""
source_extract.diagrams.detection.ring_detector — Small drawn circles (compound compositions, ring symbols).
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from scipy import ndimage

from source_extract.diagrams.models.line_scale import LineScale

_DIAMETER_PX = (6.0, 30.0)
_MIN_CIRCULARITY = 0.75
_TEXT_COMPONENT_PX = 45
_WHITE_RING_PX = 8.0


def detect_rings(
    mask: np.ndarray,
    diameter_px: tuple[float, float] | None = None,
    scale: LineScale | None = None,
) -> list[tuple[float, float, float]]:
    """Centres and hole diameters ``(x, y, d)`` of round holes (default 6–30 px) enclosed by a thin stroke.

    A hole inside a small component with a similar-sized small component close
    by in any direction (letters 'o', '0', '6', … of a label, also rotated) is skipped.
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    diameter_px = diameter_px or (s.length(_DIAMETER_PX[0]), s.length(_DIAMETER_PX[1]))
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return []
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3), bool))
    boxes = ndimage.find_objects(labels)
    rings = []
    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] < 0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        diameter = (w + h) / 2.0
        if not diameter_px[0] <= diameter <= diameter_px[1] or not 0.8 <= w / h <= 1.25:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0 or 4.0 * math.pi * cv2.contourArea(contour) / perimeter ** 2 < _MIN_CIRCULARITY:
            continue
        cx, cy = x + w / 2.0, y + h / 2.0
        if not _thin_annulus(mask, cx, cy, diameter / 2.0, s.length(_WHITE_RING_PX)):
            continue
        component = _component_at(labels, cx, cy, diameter / 2.0 + 0.5)
        if component and _is_text(boxes, component, s.length(_TEXT_COMPONENT_PX)):
            continue
        rings.append((cx, cy, diameter))
    return rings


def _thin_annulus(mask: np.ndarray, cx: float, cy: float, radius: float, white_px: float) -> bool:
    """Ink all round on the stroke (the hole contour runs on its inner edge), mostly white a few pixels further out."""
    def ink_fraction(r: float) -> float:
        angles = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
        xs = np.clip(np.round(cx + r * np.cos(angles)).astype(int), 0, mask.shape[1] - 1)
        ys = np.clip(np.round(cy + r * np.sin(angles)).astype(int), 0, mask.shape[0] - 1)
        return float(mask[ys, xs].mean())

    return ink_fraction(radius + 0.5) >= 0.85 and ink_fraction(radius + white_px) <= 0.5


def _component_at(labels: np.ndarray, cx: float, cy: float, radius: float) -> int:
    for angle in np.linspace(0.0, 2.0 * math.pi, 16, endpoint=False):
        x = int(np.clip(round(cx + radius * math.cos(angle)), 0, labels.shape[1] - 1))
        y = int(np.clip(round(cy + radius * math.sin(angle)), 0, labels.shape[0] - 1))
        if labels[y, x]:
            return int(labels[y, x])
    return 0


def _is_text(boxes: list, component: int, text_px: float) -> bool:
    box = boxes[component - 1]
    height, width = box[0].stop - box[0].start, box[1].stop - box[1].start
    if max(height, width) > text_px:
        return False
    size = max(height, width)
    for other, neighbour in enumerate(boxes, start=1):
        if other == component or neighbour is None:
            continue
        n_size = max(neighbour[0].stop - neighbour[0].start, neighbour[1].stop - neighbour[1].start)
        if n_size > text_px or n_size < 0.5 * size:
            continue
        gap_y = max(neighbour[0].start - box[0].stop, box[0].start - neighbour[0].stop)
        gap_x = max(neighbour[1].start - box[1].stop, box[1].start - neighbour[1].stop)
        if max(gap_x, gap_y) < 0.6 * size:
            return True
    return False

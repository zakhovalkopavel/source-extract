"""
source_extract.diagrams.detection.tick_detector — Tick marks along the bottom, left and right frame edges.
"""
from __future__ import annotations

import numpy as np

from source_extract.diagrams.models.frame import Frame

_BAND = 20
_MIN_INK = 5
_LONG_LINE = 15
_MAX_TICK_WIDTH = 9


def detect_ticks(mask: np.ndarray, frame: Frame) -> dict[str, list[float]]:
    """Tick centre positions: ``bottom`` → x pixels on the bottom edge, ``left`` / ``right`` → y pixels on the side edges.

    A tick is a short perpendicular run touching the inside of the edge: at
    least 5 ink pixels in a 20 px band next to the line, and no ink continuing
    past the band (that would be a curve or a compound line).
    """
    half = frame.line_width / 2.0 + 2.0
    corners = frame.corners()
    x_start = corners["bottomLeft"][0] + half + 1
    x_end = corners["bottomRight"][0] - half - 1
    bottom_profile = []
    xs = np.arange(int(np.ceil(x_start)), int(np.floor(x_end)) + 1)
    for x in xs:
        y_edge = frame.bottom_y(x)
        band_top = int(round(y_edge - half - _BAND))
        band_bottom = int(round(y_edge - half))
        band = mask[band_top:band_bottom, x]
        beyond = mask[band_top - _LONG_LINE:band_top, x]
        bottom_profile.append(int(band.sum()) if beyond.sum() < 3 else 0)

    y_start = corners["topLeft"][1] + half + 1
    y_end = corners["bottomLeft"][1] - half - 1
    left_profile = []
    ys = np.arange(int(np.ceil(y_start)), int(np.floor(y_end)) + 1)
    for y in ys:
        x_edge = frame.left_x(y)
        band_left = int(round(x_edge + half))
        band_right = int(round(x_edge + half + _BAND))
        band = mask[y, band_left:band_right]
        beyond = mask[y, band_right:band_right + _LONG_LINE]
        left_profile.append(int(band.sum()) if beyond.sum() < 3 else 0)

    y_start_right = corners["topRight"][1] + half + 1
    y_end_right = corners["bottomRight"][1] - half - 1
    right_profile = []
    ys_right = np.arange(int(np.ceil(y_start_right)), int(np.floor(y_end_right)) + 1)
    for y in ys_right:
        x_edge = frame.right_x(y)
        band_right = int(round(x_edge - half))
        band_left = int(round(x_edge - half - _BAND))
        band = mask[y, band_left:band_right]
        beyond = mask[y, band_left - _LONG_LINE:band_left]
        right_profile.append(int(band.sum()) if beyond.sum() < 3 else 0)

    return {
        "bottom": _clusters(xs, np.array(bottom_profile)),
        "left": _clusters(ys, np.array(left_profile)),
        "right": _clusters(ys_right, np.array(right_profile)),
    }


def _clusters(positions: np.ndarray, profile: np.ndarray) -> list[float]:
    hits = profile >= _MIN_INK
    centres: list[float] = []
    index = 0
    while index < len(hits):
        if not hits[index]:
            index += 1
            continue
        end = index
        while end + 1 < len(hits) and hits[end + 1]:
            end += 1
        if end - index + 1 <= _MAX_TICK_WIDTH:
            weights = profile[index:end + 1].astype(float)
            centres.append(float(np.average(positions[index:end + 1], weights=weights)))
        index = end + 1
    return centres

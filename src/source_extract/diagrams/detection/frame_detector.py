"""
source_extract.diagrams.detection.frame_detector — Find the plot frame of a binary diagram.
"""
from __future__ import annotations

import cv2
import numpy as np

from source_extract.diagrams.models.frame import Frame

_EDGE_WINDOW = 50


def detect_frame(mask: np.ndarray, search_box: tuple[int, int, int, int]) -> Frame:
    """Frame lines inside ``search_box`` (x0, y0, x1, y1).

    The frame is the connected ink component with the largest bounding box
    spanning at least 70 % of the box in both directions. Each edge is refined by
    a robust line fit through the outermost ink run of the component.
    """
    x0, y0, x1, y1 = search_box
    sub = mask[y0:y1, x0:x1].astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
    width, height = x1 - x0, y1 - y0
    best, best_area = None, 0
    for index in range(1, count):
        bx, by, bw, bh, _ = stats[index]
        if bw >= 0.7 * width or bh >= 0.7 * height:
            if bw >= 0.5 * width and bh >= 0.5 * height and bw * bh > best_area:
                best, best_area = index, bw * bh
    if best is None:
        raise ValueError(f"no frame found in search box {search_box}")
    component = labels == best
    bx, by, bw, bh, _ = stats[best]

    bottom, w_bottom = _fit_horizontal(component, bx, bx + bw, by + bh - _EDGE_WINDOW, by + bh, lowest=True)
    top, w_top = _fit_horizontal(component, bx, bx + bw, by, by + _EDGE_WINDOW, lowest=False)
    left, w_left = _fit_vertical(component, by, by + bh, bx, bx + _EDGE_WINDOW, rightmost=False)
    right, w_right = _fit_vertical(component, by, by + bh, bx + bw - _EDGE_WINDOW, bx + bw, rightmost=True)

    def shift_h(line):  # sub-image → page coordinates for y = a + s·x
        a, s = line
        return (a + y0 - s * x0, s)

    def shift_v(line):  # x = a + s·y
        a, s = line
        return (a + x0 - s * y0, s)

    return Frame(
        top=shift_h(top),
        bottom=shift_h(bottom),
        left=shift_v(left),
        right=shift_v(right),
        line_width=float(np.median([w_bottom, w_top, w_left, w_right])),
    )


def _runs(column: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate([[0], column.astype(np.int8), [0]])
    diff = np.diff(padded)
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1) - 1
    return list(zip(starts, ends))


def _robust_line(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    keep = np.ones(len(xs), bool)
    fit = (float(np.median(ys)), 0.0)
    for _ in range(5):
        if keep.sum() < 2:
            break
        slope, offset = np.polyfit(xs[keep], ys[keep], 1)
        fit = (float(offset), float(slope))
        residual = np.abs(ys - (offset + slope * xs))
        new_keep = residual <= max(1.5, 2.5 * np.median(residual[keep]))
        if np.array_equal(new_keep, keep):
            break
        keep = new_keep
    return fit


def _fit_horizontal(component, xa, xb, ya, yb, lowest: bool):
    ya, yb = max(0, ya), min(component.shape[0], yb)
    margin = int(0.05 * (xb - xa))
    xs, ys, widths = [], [], []
    for x in range(xa + margin, xb - margin, 3):
        runs = _runs(component[ya:yb, x])
        if not runs:
            continue
        start, end = runs[-1] if lowest else runs[0]
        xs.append(x)
        ys.append(ya + (start + end) / 2.0)
        widths.append(end - start + 1)
    if len(xs) < 10:
        raise ValueError("frame edge not found")
    return _robust_line(np.array(xs, float), np.array(ys, float)), float(np.median(widths))


def _fit_vertical(component, ya, yb, xa, xb, rightmost: bool):
    xa, xb = max(0, xa), min(component.shape[1], xb)
    margin = int(0.05 * (yb - ya))
    ys, xs, widths = [], [], []
    for y in range(ya + margin, yb - margin, 3):
        runs = _runs(component[y, xa:xb])
        if not runs:
            continue
        start, end = runs[-1] if rightmost else runs[0]
        ys.append(y)
        xs.append(xa + (start + end) / 2.0)
        widths.append(end - start + 1)
    if len(ys) < 10:
        raise ValueError("frame edge not found")
    return _robust_line(np.array(ys, float), np.array(xs, float)), float(np.median(widths))

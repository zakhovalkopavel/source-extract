"""Rebuild contour polylines from edited waypoints."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from source_extract.review.barycentric import Point2, Wt3, page_pixel_to_wt, page_to_image_pixel, wt_to_page_pixel
from source_extract.review.retrace_util import _dedupe, polylines_cross
from source_extract.review.retrace_smooth import (
    control_wt_to_smooth_image_pixels,
    heal_control_wt_order,
    order_control_wt_nearest,
    rebuild_smooth_from_control_wt,
    smooth_curve_from_image_waypoints,
)

def densify_polyline_wt(
    waypoints: Sequence[Sequence[float]],
    *,
    max_segment_wt: float = 1.5,
) -> list[list[float]]:
    """Insert interpolated points between waypoints so segments stay short in wt% space."""
    if len(waypoints) < 2:
        return [list(map(float, p)) for p in waypoints]
    out: list[list[float]] = [list(map(float, waypoints[0]))]
    for i in range(1, len(waypoints)):
        a = np.asarray(waypoints[i - 1], dtype=float)
        b = np.asarray(waypoints[i], dtype=float)
        dist = float(np.linalg.norm(a - b))
        n = max(1, int(np.ceil(dist / max_segment_wt)))
        for k in range(1, n + 1):
            t = k / n
            p = (1.0 - t) * a + t * b
            s = float(p.sum())
            if s > 0:
                p = p * (100.0 / s)
            out.append([round(float(v), 2) for v in p])
    return _dedupe(out)


def densify_from_image_waypoints(
    image_waypoints: Sequence[Point2],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    max_segment_wt: float = 1.5,
) -> list[list[float]]:
    """Convert image-pixel waypoints → densified polyline_wt."""
    wts: list[Wt3] = []
    for ix, iy in image_waypoints:
        page = (ix + origin[0], iy + origin[1])
        wts.append(page_pixel_to_wt(page, corners))
    return densify_polyline_wt(wts, max_segment_wt=max_segment_wt)


def polyline_wt_to_image_pixels(
    polyline_wt: Sequence[Sequence[float] | dict],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    components: Sequence[str] | None = None,
) -> list[list[float]]:
    pixels: list[list[float]] = []
    for wt in polyline_wt:
        page = wt_to_page_pixel(wt, corners, components=components)
        pixels.append([round(page[0] - origin[0], 2), round(page[1] - origin[1], 2)])
    return pixels


# Re-exports for callers that import from retrace
from source_extract.review.retrace_smooth import (  # noqa: E402
    control_wt_to_smooth_image_pixels,
    heal_control_wt_order,
    order_control_wt_nearest,
    order_image_waypoints_nearest,
    rebuild_smooth_from_control_wt,
    smooth_curve_from_image_waypoints,
    smooth_image_polyline,
)
from source_extract.review.retrace_util import polylines_cross  # noqa: E402

__all__ = [
    "densify_polyline_wt",
    "densify_from_image_waypoints",
    "polyline_wt_to_image_pixels",
    "control_wt_to_smooth_image_pixels",
    "heal_control_wt_order",
    "order_control_wt_nearest",
    "order_image_waypoints_nearest",
    "rebuild_smooth_from_control_wt",
    "smooth_curve_from_image_waypoints",
    "smooth_image_polyline",
    "polylines_cross",
]

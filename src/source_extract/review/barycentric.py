"""Composition ↔ page/image pixel conversion for ternary diagrams."""

from __future__ import annotations

from typing import Sequence


Point2 = tuple[float, float]
Wt3 = tuple[float, float, float]


def normalize_wt(wt: Sequence[float] | dict, components: Sequence[str] | None = None) -> Wt3:
    """Accept [A,B,C] lists or {component: wt%} dicts."""
    if isinstance(wt, dict):
        if components is None:
            # stable order by insertion if no components provided
            vals = list(wt.values())
            if len(vals) != 3:
                raise ValueError(f"Expected 3 wt% values, got {wt!r}")
            return (float(vals[0]), float(vals[1]), float(vals[2]))
        return (float(wt[components[0]]), float(wt[components[1]]), float(wt[components[2]]))
    return (float(wt[0]), float(wt[1]), float(wt[2]))


def wt_to_page_pixel(
    wt: Sequence[float] | dict,
    corners: Sequence[Point2],
    components: Sequence[str] | None = None,
) -> Point2:
    """Map [A,B,C] wt% to page pixel using triangle corner pixels (same order as components)."""
    a, b, c = normalize_wt(wt, components)
    a, b, c = a / 100.0, b / 100.0, c / 100.0
    x = a * corners[0][0] + b * corners[1][0] + c * corners[2][0]
    y = a * corners[0][1] + b * corners[1][1] + c * corners[2][1]
    return (x, y)


def page_to_image_pixel(page: Point2, origin: Point2) -> Point2:
    return (page[0] - origin[0], page[1] - origin[1])


def image_to_page_pixel(image: Point2, origin: Point2) -> Point2:
    return (image[0] + origin[0], image[1] + origin[1])


def page_pixel_to_wt(page: Point2, corners: Sequence[Point2]) -> Wt3:
    """Barycentric solve for page pixel → wt% (clamped to the triangle)."""
    (x1, y1), (x2, y2), (x3, y3) = corners
    x, y = page
    denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denom) < 1e-12:
        return (100.0 / 3.0, 100.0 / 3.0, 100.0 / 3.0)
    a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom
    b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom
    c = 1.0 - a - b
    # Clamp negative barycentric coords (outside triangle)
    a, b, c = max(a, 0.0), max(b, 0.0), max(c, 0.0)
    s = a + b + c
    if s <= 0:
        return (100.0 / 3.0, 100.0 / 3.0, 100.0 / 3.0)
    a, b, c = a / s, b / s, c / s
    return (round(a * 100.0, 2), round(b * 100.0, 2), round(c * 100.0, 2))


def corners_from_calibration(components: Sequence[str], calibration: dict) -> list[Point2]:
    """Build corner pixel list in component order from digitization.calibration."""
    out: list[Point2] = []
    for name in components:
        if name not in calibration:
            raise KeyError(f"Missing calibration corner for {name}")
        xy = calibration[name]
        out.append((float(xy[0]), float(xy[1])))
    return out

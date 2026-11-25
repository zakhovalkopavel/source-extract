"""Small polyline helpers shared by densify and smooth retrace."""

from __future__ import annotations

from typing import Sequence

from source_extract.review.barycentric import Point2

def _dedupe(points: list[list[float]], eps: float = 1e-6) -> list[list[float]]:
    if not points:
        return points
    out = [points[0]]
    for p in points[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps or abs(p[2] - out[-1][2]) > eps:
            out.append(p)
    return out


def _segments_properly_intersect(
    a: Point2,
    b: Point2,
    c: Point2,
    d: Point2,
    *,
    eps: float = 1e-9,
) -> bool:
    """True when segment AB crosses CD in the relative interior (shared endpoints ignored)."""
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    dx, dy = float(d[0]), float(d[1])
    den = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(den) < eps:
        return False  # parallel / collinear — treat as non-crossing
    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / den
    u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / den
    return eps < t < 1.0 - eps and eps < u < 1.0 - eps


def polylines_cross(poly_a: Sequence[Point2], poly_b: Sequence[Point2]) -> bool:
    """Return True if two image-space polylines properly intersect."""
    if len(poly_a) < 2 or len(poly_b) < 2:
        return False
    for i in range(len(poly_a) - 1):
        a, b = poly_a[i], poly_a[i + 1]
        for j in range(len(poly_b) - 1):
            if _segments_properly_intersect(a, b, poly_b[j], poly_b[j + 1]):
                return True
    return False


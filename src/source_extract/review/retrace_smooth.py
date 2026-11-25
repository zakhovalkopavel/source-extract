"""Shape-preserving cubic Hermite smoothing for image-space polylines."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from source_extract.review.barycentric import Point2, page_pixel_to_wt, page_to_image_pixel, wt_to_page_pixel
from source_extract.review.retrace_util import _dedupe

def _chord_parameters(pts: Sequence[np.ndarray]) -> list[float]:
    """Cumulative chord length along control points (parameter for cubic Hermite)."""
    s = [0.0]
    for i in range(1, len(pts)):
        s.append(s[-1] + float(np.linalg.norm(pts[i] - pts[i - 1])))
    return s


def _fritsch_carlson_slopes(s: Sequence[float], v: Sequence[float]) -> list[float]:
    """Shape-preserving slopes for cubic Hermite — no new extrema between knots.

    Fritsch–Carlson / Brodlie monotone cubic construction on a scalar series v(s).
    Between consecutive knots the interpolant is cubic (degree ≤ 3) and does not
    overshoot the local data range (no spurious local max/min on open intervals).
    """
    n = len(v)
    if n < 2:
        return [0.0] * n
    delta = [0.0] * (n - 1)
    for i in range(n - 1):
        h = s[i + 1] - s[i]
        delta[i] = 0.0 if abs(h) < 1e-15 else (v[i + 1] - v[i]) / h

    m = [0.0] * n
    m[0] = delta[0]
    m[-1] = delta[-1]
    for i in range(1, n - 1):
        if delta[i - 1] * delta[i] <= 0.0:
            m[i] = 0.0
        else:
            w1 = 2.0 * (s[i + 1] - s[i]) + (s[i] - s[i - 1])
            w2 = (s[i + 1] - s[i]) + 2.0 * (s[i] - s[i - 1])
            m[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])

    # Limit slopes so the cubic does not introduce extrema on each segment
    for i in range(n - 1):
        if abs(delta[i]) < 1e-15:
            m[i] = 0.0
            m[i + 1] = 0.0
            continue
        alpha = m[i] / delta[i]
        beta = m[i + 1] / delta[i]
        tau = alpha * alpha + beta * beta
        if tau > 9.0:
            scale = 3.0 / (tau**0.5)
            m[i] = scale * alpha * delta[i]
            m[i + 1] = scale * beta * delta[i]
    return m


def _hermite_cubic(v0: float, v1: float, m0: float, m1: float, h: float, t: float) -> float:
    """Evaluate cubic Hermite on [0,1] (degree ≤ 3)."""
    t2 = t * t
    t3 = t2 * t
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2
    return h00 * v0 + h10 * h * m0 + h01 * v1 + h11 * h * m1


def order_image_waypoints_nearest(image_waypoints: Sequence[Point2]) -> list[Point2]:
    """Reorder waypoints into an open nearest-neighbor path (click order ignored).

    Starts from both ends of the farthest pair and keeps the shorter chain so the
    curve follows closest points instead of the sequence the user clicked.
    """
    pts = [(float(p[0]), float(p[1])) for p in image_waypoints]
    n = len(pts)
    if n <= 2:
        return pts

    def dist2(i: int, j: int) -> float:
        dx = pts[i][0] - pts[j][0]
        dy = pts[i][1] - pts[j][1]
        return dx * dx + dy * dy

    best_i, best_j, best_d = 0, 1, -1.0
    for i in range(n):
        for j in range(i + 1, n):
            d = dist2(i, j)
            if d > best_d:
                best_i, best_j, best_d = i, j, d

    def chain(start: int) -> list[int]:
        used = [False] * n
        order = [start]
        used[start] = True
        while len(order) < n:
            cur = order[-1]
            nxt, nd = -1, float("inf")
            for k in range(n):
                if used[k]:
                    continue
                d = dist2(cur, k)
                if d < nd:
                    nxt, nd = k, d
            order.append(nxt)
            used[nxt] = True
        return order

    def path_len(order: list[int]) -> float:
        return sum(dist2(order[i], order[i + 1]) for i in range(len(order) - 1))

    o1 = chain(best_i)
    o2 = chain(best_j)
    order = o1 if path_len(o1) <= path_len(o2) else o2
    return [pts[i] for i in order]


def smooth_image_polyline(
    image_waypoints: Sequence[Point2],
    *,
    samples_per_segment: int = 32,
) -> list[Point2]:
    """Dense image-space polyline through controls (shape-preserving cubics).

    Between each consecutive pair the path is a cubic Hermite polynomial
    (degree ≤ 3) in chord length. Slopes use Fritsch–Carlson limiting so each
    coordinate has **no new extrema** between knots (no Catmull–Rom overshoot).

    2 points → samples along the chord (degree 1).
    """
    pts = [np.asarray([float(p[0]), float(p[1])], dtype=float) for p in image_waypoints]
    if len(pts) < 2:
        raise ValueError("Need at least 2 waypoints")
    if len(pts) == 2:
        a, b = pts
        n = max(16, samples_per_segment)
        return [
            (float((1 - t) * a[0] + t * b[0]), float((1 - t) * a[1] + t * b[1]))
            for t in np.linspace(0, 1, n)
        ]

    s = _chord_parameters(pts)
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    mx = _fritsch_carlson_slopes(s, xs)
    my = _fritsch_carlson_slopes(s, ys)

    dense: list[Point2] = [(xs[0], ys[0])]
    n_seg = max(8, samples_per_segment)
    for i in range(len(pts) - 1):
        h = s[i + 1] - s[i]
        if h < 1e-15:
            continue
        # Interior samples of this cubic segment (skip t=0; include t=1)
        for k in range(1, n_seg + 1):
            t = k / n_seg
            x = _hermite_cubic(xs[i], xs[i + 1], mx[i], mx[i + 1], h, t)
            y = _hermite_cubic(ys[i], ys[i + 1], my[i], my[i + 1], h, t)
            dense.append((float(x), float(y)))
    return dense


def smooth_curve_from_image_waypoints(
    image_waypoints: Sequence[Point2],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    samples_per_segment: int = 32,
    reorder_nearest: bool = True,
) -> tuple[list[list[float]], list[list[float]]]:
    """Fit a smooth curve through image waypoints → (control_wt, dense polyline_wt).

    When ``reorder_nearest`` is True (default for seed builds), waypoints are
    sorted into a nearest-neighbor path so click order does not matter.
    """
    pts = [(float(p[0]), float(p[1])) for p in image_waypoints]
    if len(pts) < 2:
        raise ValueError("Need at least 2 waypoints")
    if reorder_nearest:
        pts = order_image_waypoints_nearest(pts)

    control_wt: list[list[float]] = []
    for ix, iy in pts:
        page = (ix + origin[0], iy + origin[1])
        control_wt.append([round(v, 2) for v in page_pixel_to_wt(page, corners)])

    dense_img = smooth_image_polyline(pts, samples_per_segment=samples_per_segment)
    dense_wt: list[list[float]] = []
    for ix, iy in dense_img:
        page = (ix + origin[0], iy + origin[1])
        dense_wt.append([round(v, 2) for v in page_pixel_to_wt(page, corners)])
    return control_wt, _dedupe(dense_wt)


def _image_path_length(pts: Sequence[Point2]) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        dx = float(pts[i + 1][0]) - float(pts[i][0])
        dy = float(pts[i + 1][1]) - float(pts[i][1])
        total += (dx * dx + dy * dy) ** 0.5
    return total


def order_control_wt_nearest(
    control_wt: Sequence[Sequence[float]],
    *,
    corners: Sequence[Point2],
    origin: Point2,
) -> list[list[float]]:
    """Reorder control_wt into an open nearest-neighbor path in image space."""
    if len(control_wt) <= 2:
        return [list(map(float, p)) for p in control_wt]
    img: list[Point2] = []
    for wt in control_wt:
        page = wt_to_page_pixel(wt, corners)
        img.append(page_to_image_pixel(page, origin))
    ordered_img = order_image_waypoints_nearest(img)
    out: list[list[float]] = []
    for ix, iy in ordered_img:
        page = (ix + origin[0], iy + origin[1])
        out.append([round(float(v), 2) for v in page_pixel_to_wt(page, corners)])
    return out


def heal_control_wt_order(
    control_wt: Sequence[Sequence[float]],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    max_ratio: float = 1.12,
) -> list[list[float]] | None:
    """Return NN-reordered controls when the current path is much longer; else None."""
    if len(control_wt) < 3:
        return None
    img: list[Point2] = []
    for wt in control_wt:
        page = wt_to_page_pixel(wt, corners)
        img.append(page_to_image_pixel(page, origin))
    ordered_img = order_image_waypoints_nearest(img)
    before = _image_path_length(img)
    after = _image_path_length(ordered_img)
    if after <= 1e-9 or before / after <= max_ratio:
        return None
    out: list[list[float]] = []
    for ix, iy in ordered_img:
        page = (ix + origin[0], iy + origin[1])
        out.append([round(float(v), 2) for v in page_pixel_to_wt(page, corners)])
    return out


def rebuild_smooth_from_control_wt(
    control_wt: Sequence[Sequence[float]],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    samples_per_segment: int = 32,
    reorder_nearest: bool = False,
) -> list[list[float]]:
    """Rebuild dense polyline_wt from control_wt via image-space smooth curve."""
    if len(control_wt) < 2:
        return [list(map(float, p)) for p in control_wt]
    img: list[Point2] = []
    for wt in control_wt:
        page = wt_to_page_pixel(wt, corners)
        img.append(page_to_image_pixel(page, origin))
    _controls, dense = smooth_curve_from_image_waypoints(
        img,
        corners=corners,
        origin=origin,
        samples_per_segment=samples_per_segment,
        reorder_nearest=reorder_nearest,
    )
    return dense


def control_wt_to_smooth_image_pixels(
    control_wt: Sequence[Sequence[float]],
    *,
    corners: Sequence[Point2],
    origin: Point2,
    samples_per_segment: int = 32,
) -> tuple[list[list[float]], list[list[float]]]:
    """Return (control_image_pixels, dense_smooth_image_pixels) for canvas drawing."""
    ctrl_img: list[list[float]] = []
    for wt in control_wt:
        page = wt_to_page_pixel(wt, corners)
        ix, iy = page_to_image_pixel(page, origin)
        ctrl_img.append([round(ix, 2), round(iy, 2)])
    if len(ctrl_img) < 2:
        return ctrl_img, list(ctrl_img)
    dense = smooth_image_polyline(
        [(p[0], p[1]) for p in ctrl_img],
        samples_per_segment=samples_per_segment,
    )
    return ctrl_img, [[round(x, 2), round(y, 2)] for x, y in dense]


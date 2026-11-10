"""
source_extract.diagrams.detection.triangle_detector — Find the composition triangles of ternary diagrams on a page.
"""
from __future__ import annotations

import itertools
import math

import cv2
import numpy as np

from source_extract.diagrams.models.line_scale import LineScale

_MIN_SIDE_FRACTION = 0.1
_ANGLE_DEG = 6.0
_MERGE_ANGLE_DEG = 1.5
_MERGE_OFFSET_PX = 8.0
_MERGE_GAP_PX = 40.0
_COVER = 0.7
_OVERSHOOT = 0.15
_SIDE_RATIO = 0.1
_SAME_CORNER = 0.03
_FIT_BAND_PX = 6.0
_FIT_TRIM = 0.1


def detect_triangles(mask: np.ndarray, scale: LineScale | None = None) -> list[tuple[tuple[float, float], ...]]:
    """Corners ``(top, left, right)`` (page pixels) of each apex-up triangle with 60° angles, largest first.

    Long straight ink lines (probabilistic Hough, at least 10 % of the shorter page
    side) are merged when collinear and at most 40 px apart along the line (the bases
    of side-by-side figures on a skewed scan are collinear but not one line). Three
    lines whose directions differ by 60° (± 6°) form a triangle when none overshoots a
    corner by more than 15 % of the side, the sides agree within 10 %, and ink lies
    within 6 px of at least 70 % of each side between the two corners (Hough splits
    long scanned lines into pieces). Each side is then refined by a least-squares
    line through the ink
    within 6 px of it (the middle 80 % of the side) and the corners are the
    intersections of the refined lines. Triangles sharing their corners (within 3 %
    of the side) are reported once. Pixel sizes are for the reference line width,
    scaled by ``scale``.
    """
    s = scale or LineScale()
    min_side = _MIN_SIDE_FRACTION * min(mask.shape)
    found = cv2.HoughLinesP(mask.astype(np.uint8) * 255, 1, math.pi / 720, threshold=int(min_side / 2),
                            minLineLength=int(min_side), maxLineGap=s.count(8))
    lines = _merged([tuple(float(v) for v in f[0]) for f in found] if found is not None else [], s)
    triangles: list[tuple[tuple[float, float], ...]] = []
    for a, b, c in itertools.combinations(lines, 3):
        corners = _triangle(a, b, c, mask, s.length(_FIT_BAND_PX))
        if corners is None or max(_side(corners)) < min_side:
            continue
        refined = _refine(mask, corners, s)
        side = max(_side(refined))
        if all(min(math.dist(p, q) for q in t) > _SAME_CORNER * side for t in triangles for p in refined):
            triangles.append(refined)
    return sorted(triangles, key=lambda t: -max(_side(t)))


def _angle(line) -> float:
    x0, y0, x1, y1 = line
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0


def _angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _merged(segments, s: LineScale) -> list[tuple[float, float, float, float]]:
    """Collinear segments joined into lines; a gap of more than ``_MERGE_GAP_PX`` along the line starts a new one."""
    groups: list[list] = []
    for seg in sorted(segments, key=lambda g: -math.dist(g[:2], g[2:])):
        angle = _angle(seg)
        for group in groups:
            ref = group[0]
            if _angle_gap(angle, _angle(ref)) <= _MERGE_ANGLE_DEG and \
                    max(_offset(ref, seg[:2]), _offset(ref, seg[2:])) <= s.length(_MERGE_OFFSET_PX):
                group.append(seg)
                break
        else:
            groups.append([seg])
    gap = s.length(_MERGE_GAP_PX)
    out = []
    for group in groups:
        ref = group[0]
        direction = np.array(ref[2:]) - np.array(ref[:2])
        direction /= np.linalg.norm(direction)
        origin = np.array(ref[:2])
        spans = sorted(sorted(float((np.array(p) - origin) @ direction) for p in (g[:2], g[2:])) for g in group)
        runs = [list(spans[0])]
        for t0, t1 in spans[1:]:
            if t0 > runs[-1][1] + gap:
                runs.append([t0, t1])
            else:
                runs[-1][1] = max(runs[-1][1], t1)
        for t0, t1 in runs:
            start, end = origin + t0 * direction, origin + t1 * direction
            out.append((float(start[0]), float(start[1]), float(end[0]), float(end[1])))
    return out


def _offset(line, point) -> float:
    x0, y0, x1, y1 = line
    dx, dy = x1 - x0, y1 - y0
    return abs((point[0] - x0) * dy - (point[1] - y0) * dx) / math.hypot(dx, dy)


def _intersection(a, b) -> tuple[float, float] | None:
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def _triangle(a, b, c, mask: np.ndarray, band: float) -> tuple[tuple[float, float], ...] | None:
    angles = [_angle(line) for line in (a, b, c)]
    if any(abs(_angle_gap(p, q) - 60.0) > _ANGLE_DEG for p, q in itertools.combinations(angles, 2)):
        return None
    pairs = ((a, b), (b, c), (c, a))
    points = [_intersection(p, q) for p, q in pairs]
    if any(p is None for p in points):
        return None
    ends = {0: (points[2], points[0]), 1: (points[0], points[1]), 2: (points[1], points[2])}
    for index, line in enumerate((a, b, c)):
        p, q = ends[index]
        side = math.dist(p, q)
        if side <= 0:
            return None
        direction = (np.array(q) - np.array(p)) / side
        ts = sorted(float((np.array(e) - np.array(p)) @ direction) for e in (line[:2], line[2:]))
        if ts[0] < -_OVERSHOOT * side or ts[1] > (1 + _OVERSHOOT) * side:
            return None
    sides = _side(points)
    if max(sides) - min(sides) > _SIDE_RATIO * max(sides):
        return None
    if any(_ink_cover(mask, points[i], points[(i + 1) % 3], band) < _COVER for i in range(3)):
        return None
    return _ordered(points)


def _ink_cover(mask: np.ndarray, p, q, band: float) -> float:
    """Fraction of the points of segment p–q (1 px apart) with ink within ``band`` across it."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    length = float(np.linalg.norm(q - p))
    direction = (q - p) / length
    normal = np.array([-direction[1], direction[0]])
    along = np.linspace(0.0, length, max(2, int(length)))
    across = np.arange(-math.floor(band), math.floor(band) + 1)
    points = p + along[:, None, None] * direction + across[None, :, None] * normal
    xs, ys = np.rint(points[..., 0]).astype(int), np.rint(points[..., 1]).astype(int)
    inside = (xs >= 0) & (xs < mask.shape[1]) & (ys >= 0) & (ys < mask.shape[0])
    ink = np.zeros(xs.shape, bool)
    ink[inside] = mask[ys[inside], xs[inside]]
    return float(ink.any(axis=1).mean())


def _ordered(points) -> tuple[tuple[float, float], ...]:
    top = min(points, key=lambda p: p[1])
    left, right = sorted((p for p in points if p is not top), key=lambda p: p[0])
    return (float(top[0]), float(top[1])), (float(left[0]), float(left[1])), (float(right[0]), float(right[1]))


def _side(corners) -> list[float]:
    return [math.dist(corners[i], corners[(i + 1) % 3]) for i in range(3)]


def _refine(mask: np.ndarray, corners, s: LineScale) -> tuple[tuple[float, float], ...]:
    """Corners from least-squares lines through the ink along each side."""
    band = s.length(_FIT_BAND_PX)
    ys, xs = np.nonzero(mask)
    lines = []
    for i in range(3):
        p, q = np.array(corners[i]), np.array(corners[(i + 1) % 3])
        length = float(np.linalg.norm(q - p))
        direction = (q - p) / length
        normal = np.array([-direction[1], direction[0]])
        x0, x1 = sorted((p[0], q[0]))
        y0, y1 = sorted((p[1], q[1]))
        near = (xs >= x0 - band) & (xs <= x1 + band) & (ys >= y0 - band) & (ys <= y1 + band)
        points = np.stack([xs[near], ys[near]], axis=1).astype(float)
        t = (points - p) @ direction
        d = (points - p) @ normal
        keep = (np.abs(d) <= band) & (t >= _FIT_TRIM * length) & (t <= (1 - _FIT_TRIM) * length)
        if keep.sum() < 10:
            lines.append((*p, *q))
            continue
        chosen = points[keep]
        centre = chosen.mean(axis=0)
        _, _, vt = np.linalg.svd(chosen - centre, full_matrices=False)
        along = vt[0]
        lines.append((*centre, *(centre + along * length)))
    points = [_intersection(lines[i], lines[(i + 1) % 3]) for i in range(3)]
    if any(p is None for p in points):
        return corners
    return _ordered([points[2], points[0], points[1]])

"""
source_extract.diagrams.detection.text_detector — Boxes of printed labels (digits, letters) on a diagram.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from source_extract.diagrams.models.line_scale import LineScale

_SIZE_PX = (14, 50)
_MAX_BLOB_PX = 90
_SIZE_RATIO = 1.6
_GAP_FACTOR = 0.8
_MAX_ELONGATION = 3.0
_ROUND_ELONGATION = 1.6
_ALONG_AXIS_COS = 0.7
_MAX_HOLE_SIDE_PX = 25
_HOLE_AREA_PX = (12, 400)
_EXCLUDE_PX = 4.0


def detect_text_boxes(
    mask: np.ndarray,
    size_px: tuple[int, int] | None = None,
    min_glyphs: int = 3,
    max_blob_px: int | None = None,
    exclude: list[tuple[float, float]] | None = None,
    scale: LineScale | None = None,
) -> list[tuple[int, int, int, int]]:
    """Boxes ``(x0, y0, x1, y1)`` of printed labels (one box per glyph or glued blob).

    Glyph groups: components of ``size_px`` (largest box side, default 14–50 px) that are not
    long and thin (eigenvalue-ratio root < 3), at least ``min_glyphs`` linked.
    Two glyphs link when their sizes differ by at most 1.6×, the gap between
    their boxes is at most 0.8× the larger size, and each is round (root <
    1.6) or lies across the line to the other one; dashes of one dashed line
    lie along it and do not link.

    Loop blobs: digits glued together (and to a dash) form one component; a
    small enclosed hole (12–400 px, box side ≤ 25; 0, 4, 6, 8, 9, O) inside a
    component with largest box side ≤ ``max_blob_px`` (default 90 px) marks that component
    as a label. Holes and glyphs centred within 4 px of an ``exclude`` point (rings, e.g. a
    compound ring printed next to its formula) are skipped.
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    size_px = size_px or (s.count(_SIZE_PX[0]), s.count(_SIZE_PX[1]))
    max_blob_px = s.count(_MAX_BLOB_PX) if max_blob_px is None else max_blob_px
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3), bool))
    out = _loop_blobs(mask, labels, max_blob_px, exclude or [], s)
    exclude_px = s.length(_EXCLUDE_PX)
    glyphs = []
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None:
            continue
        size = max(box[0].stop - box[0].start, box[1].stop - box[1].start)
        if not size_px[0] <= size <= size_px[1]:
            continue
        ys, xs = np.nonzero(labels[box] == index)
        points = np.column_stack([xs + box[1].start, ys + box[0].start]).astype(float)
        centre = points.mean(axis=0)
        if any(np.hypot(*(centre - point)) <= exclude_px for point in exclude or []):
            continue
        values, vectors = np.linalg.eigh(np.cov((points - centre).T))
        elongation = float(np.sqrt(values[1] / max(values[0], 1e-9)))
        if elongation >= _MAX_ELONGATION:
            continue
        glyphs.append((centre, size, elongation, vectors[:, 1],
                       (box[1].start, box[0].start, box[1].stop, box[0].stop)))
    if len(glyphs) < min_glyphs:
        return out
    parent = list(range(len(glyphs)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    tree = cKDTree(np.array([g[0] for g in glyphs]))
    for i, j in tree.query_pairs(r=_GAP_FACTOR * size_px[1] + size_px[1]):
        if _pair(glyphs[i], glyphs[j]):
            parent[root(i)] = root(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(glyphs)):
        groups.setdefault(root(i), []).append(i)
    for members in groups.values():
        if len(members) >= min_glyphs:
            out.extend(tuple(int(v) for v in glyphs[i][4]) for i in members)
    return out


def _loop_blobs(mask, labels, max_blob_px, exclude, scale: LineScale) -> list[tuple[int, int, int, int]]:
    holes, count = ndimage.label(ndimage.binary_fill_holes(mask) & ~mask)
    component_boxes = ndimage.find_objects(labels)
    found: set[int] = set()
    exclude_px = scale.length(_EXCLUDE_PX)
    for index, box in enumerate(ndimage.find_objects(holes), start=1):
        if box is None or max(box[0].stop - box[0].start, box[1].stop - box[1].start) > scale.length(_MAX_HOLE_SIDE_PX):
            continue
        hole = holes[box] == index
        if not scale.area(_HOLE_AREA_PX[0]) <= hole.sum() <= scale.area(_HOLE_AREA_PX[1]):
            continue
        cy, cx = (b.start + c for b, c in zip(box, ndimage.center_of_mass(hole)))
        if any((cx - ex) ** 2 + (cy - ey) ** 2 <= exclude_px ** 2 for ex, ey in exclude):
            continue
        y0, x0 = max(box[0].start - 1, 0), max(box[1].start - 1, 0)
        around = labels[y0:box[0].stop + 1, x0:box[1].stop + 1]
        owners = around[around > 0]
        if owners.size == 0:
            continue
        owner = int(np.bincount(owners).argmax())
        cbox = component_boxes[owner - 1]
        if max(cbox[0].stop - cbox[0].start, cbox[1].stop - cbox[1].start) <= max_blob_px:
            found.add(owner)
    return [(component_boxes[i - 1][1].start, component_boxes[i - 1][0].start,
             component_boxes[i - 1][1].stop, component_boxes[i - 1][0].stop) for i in sorted(found)]


def _pair(a, b) -> bool:
    (ca, sa, ea, axis_a, box_a), (cb, sb, eb, axis_b, box_b) = a, b
    if max(sa, sb) > _SIZE_RATIO * min(sa, sb):
        return False
    gap_x = max(box_a[0], box_b[0]) - min(box_a[2], box_b[2])
    gap_y = max(box_a[1], box_b[1]) - min(box_a[3], box_b[3])
    if max(gap_x, gap_y, 0) > _GAP_FACTOR * max(sa, sb):
        return False
    direction = (cb - ca) / max(np.linalg.norm(cb - ca), 1e-9)
    return all(e < _ROUND_ELONGATION or abs(float(direction @ axis)) < _ALONG_AXIS_COS
               for e, axis in ((ea, axis_a), (eb, axis_b)))

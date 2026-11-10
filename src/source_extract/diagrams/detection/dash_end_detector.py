"""
source_extract.diagrams.detection.dash_end_detector — Where a line stopping short of another line would meet it.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from source_extract.diagrams.detection.skeletonizer import skeletonize
from source_extract.diagrams.models.line_scale import LineScale

_MIN_LINE_PX = 60
_REACH_PX = 45.0
_MIN_DASH_PX = 12
_MIN_ELONGATION = 2.0
_MAX_MEAN_WIDTH_PX = 8.0
_MIN_STROKE_ELONGATION = 3.0
_STROKE_AREA_FACTOR = 3.0
_MERGED_AREA_FACTOR = 2.5
_MIN_CROSSING_SIN = 0.4
_DIRECTION_PX = 12
_FRAME_ZONE_PX = 25.0
_LEADER_PX = 90.0
_LEADER_SLACK_PX = 2
_OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_FREE = "free"


def detect_dash_ends(
    mask: np.ndarray,
    min_line_px: int | None = None,
    reach_px: float | None = None,
    frame: np.ndarray | None = None,
    blocked: np.ndarray | None = None,
    scale: LineScale | None = None,
) -> list[tuple[float, float]]:
    """Pixels ``(x, y)`` where a line end, extended along its direction, meets another line (``detect_line_ends``)."""
    return detect_line_ends(mask, min_line_px, reach_px, frame, blocked, scale)[0]


def detect_line_ends(
    mask: np.ndarray,
    min_line_px: int | None = None,
    reach_px: float | None = None,
    frame: np.ndarray | None = None,
    blocked: np.ndarray | None = None,
    scale: LineScale | None = None,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Pixels ``(x, y)`` where a line end, extended along its direction, meets another line, and free line ends.

    Line ends are both ends of a dash (a component of 12 px up to ``min_line_px``
    (default 60 px), thin and elongated; direction = its axis) and the free skeleton ends of
    solid lines (direction over the last 12 px). Skeleton ends of the ink joined to the
    frame are skipped within 25 px of it (tick marks), so lines joined to the frame through
    other lines keep their ends. The ray runs up to ``reach_px`` (default 45 px):

    - ``frame`` (triangle edges, a few px wide): a frame pixel is the node.
      Within 25 px of the frame other solid ink (tick marks) is passed over.
    - a solid line (largest box side ≥ ``min_line_px``): the hit pixel is the node.
    - for a dash, a heavier stroke (elongated, ≥ 3× its area) or a merged
      shape that is not a dash (≥ 2.5× its area, e.g. dashes of two lines
      touching): the node is where the ray line crosses the shape's axis
      (crossing angle sine ≥ 0.4).
    - any other ink, or ``blocked`` (label boxes), ends the ray without a node.

    A solid-line end outside ``blocked`` whose ray meets no ink at all within ``reach_px``
    is a free end (an isotherm stopping in open paper); the end pixel is returned in the
    second list. Not free ends: ends within 25 px of the frame, and ends whose stroke runs
    straight back to the frame within 90 px (label leaders and ticks crossing the edge). Dashes whose box touches ``blocked`` (e.g. the digit 1 of a label) have no ends.
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    min_line_px = s.count(_MIN_LINE_PX) if min_line_px is None else min_line_px
    reach_px = s.length(_REACH_PX) if reach_px is None else reach_px
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3), bool))
    boxes = ndimage.find_objects(labels)
    count = len(boxes) + 1
    sizes = np.array([0] + [0 if b is None else max(b[0].stop - b[0].start, b[1].stop - b[1].start) for b in boxes])
    solid_ids = sizes >= min_line_px
    solid = solid_ids[labels]
    frame = np.zeros(mask.shape, bool) if frame is None else frame
    blocked = np.zeros(mask.shape, bool) if blocked is None else blocked
    zone = ndimage.distance_transform_edt(~frame) <= s.length(_FRAME_ZONE_PX) if frame.any() else np.zeros(mask.shape, bool)
    on_frame = np.zeros(count, bool)
    on_frame[np.unique(labels[frame & mask])] = True
    area = np.zeros(count)
    centres = np.zeros((count, 2))
    axes = np.zeros((count, 2))
    stroke = np.zeros(count, bool)
    dash = np.zeros(count, bool)
    ends: list[tuple[np.ndarray, np.ndarray, int]] = []
    for index, box in enumerate(boxes, start=1):
        if box is None or not s.count(_MIN_DASH_PX) <= sizes[index] < min_line_px:
            continue
        ys, xs = np.nonzero(labels[box] == index)
        points = np.column_stack([xs + box[1].start, ys + box[0].start]).astype(float)
        centre = points.mean(axis=0)
        values, vectors = np.linalg.eigh(np.cov((points - centre).T))
        area[index], centres[index], axes[index] = len(points), centre, vectors[:, 1]
        ratio = values[1] / max(values[0], 1e-9)
        stroke[index] = ratio >= _MIN_STROKE_ELONGATION ** 2
        along = (points - centre) @ vectors[:, 1]
        if ratio < _MIN_ELONGATION ** 2 or len(points) / max(along.max() - along.min(), 1.0) > s.length(_MAX_MEAN_WIDTH_PX):
            continue
        dash[index] = True
        if blocked[box].any():
            continue
        ends.append((centre + vectors[:, 1] * along.max(), vectors[:, 1], index))
        ends.append((centre + vectors[:, 1] * along.min(), -vectors[:, 1], index))
    for start, direction, own in _skeleton_ends(skeletonize(solid), labels, s.count(_DIRECTION_PX)):
        if not (on_frame[own] and zone[int(start[1]), int(start[0])]):
            ends.append((start, direction, own))
    hits, free = [], []
    for start, direction, own in ends:
        if dash[own]:
            heavy = (stroke & (area >= _STROKE_AREA_FACTOR * area[own])) | (~dash & (area >= _MERGED_AREA_FACTOR * area[own]))
        else:
            heavy = np.zeros(count, bool)
        hit = _first_hit(labels, solid_ids, heavy, frame, zone, blocked, start, direction, reach_px, own)
        if hit is _FREE:
            y, x = int(start[1]), int(start[0])
            if solid_ids[own] and not (blocked[y, x] or zone[y, x]) and not _leader(mask, frame, start, direction, s.length(_LEADER_PX)):
                free.append((float(start[0]), float(start[1])))
            continue
        if hit is None:
            continue
        point, target = hit
        if heavy[target] and not solid_ids[target]:
            point = _crossing(start, direction, centres[target], axes[target], reach_px)
        if point is not None:
            hits.append((float(point[0]), float(point[1])))
    return hits, free


def _skeleton_ends(skeleton: np.ndarray, labels: np.ndarray, steps: int) -> list[tuple[np.ndarray, np.ndarray, int]]:
    height, width = skeleton.shape
    padded = np.pad(skeleton.astype(np.int16), 1)
    count = sum(padded[1 + dy:height + 1 + dy, 1 + dx:width + 1 + dx] for dy, dx in _OFFSETS)
    out = []
    for y, x in np.argwhere(skeleton & (count == 1)):
        visited = {(y, x)}
        current = (y, x)
        for _ in range(steps):
            following = [(current[0] + dy, current[1] + dx) for dy, dx in _OFFSETS
                         if 0 <= current[0] + dy < height and 0 <= current[1] + dx < width
                         and skeleton[current[0] + dy, current[1] + dx] and (current[0] + dy, current[1] + dx) not in visited]
            if not following:
                break
            current = following[0]
            visited.add(current)
        vector = np.array([x - current[1], y - current[0]], float)
        norm = np.linalg.norm(vector)
        if norm >= steps / 2:
            out.append((np.array([x, y], float), vector / norm, int(labels[y, x])))
    return out


def _first_hit(labels, solid_ids, heavy, frame, zone, blocked, start, direction, reach, own):
    """(pixel, label) of the line hit, ``_FREE`` when the ray meets no ink, None when other ink stops it."""
    for step in range(1, int(reach) + 1):
        ix, iy = (int(round(v)) for v in start + direction * step)
        if not (0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1]):
            return None
        if frame[iy, ix]:
            return np.array([ix, iy], float), 0
        label = labels[iy, ix]
        if label == own or label == 0:
            continue
        if blocked[iy, ix]:
            return None
        if zone[iy, ix]:
            if solid_ids[label]:
                continue
            return None
        if solid_ids[label] or heavy[label]:
            return np.array([ix, iy], float), int(label)
        return None
    return _FREE


def _leader(mask, frame, start, direction, length) -> bool:
    """True if ink (within 2 px of the ray) runs straight back from the end to the frame within ``length`` (label leader, tick)."""
    height, width = mask.shape
    for step in range(1, int(length) + 1):
        ix, iy = (int(round(v)) for v in start - direction * step)
        if not (0 <= iy < height and 0 <= ix < width):
            return False
        if frame[iy, ix]:
            return True
        if not mask[max(iy - _LEADER_SLACK_PX, 0):iy + _LEADER_SLACK_PX + 1,
                    max(ix - _LEADER_SLACK_PX, 0):ix + _LEADER_SLACK_PX + 1].any():
            return False
    return False


def _crossing(start, direction, centre, axis, reach) -> np.ndarray | None:
    cross = direction[0] * axis[1] - direction[1] * axis[0]
    if abs(cross) < _MIN_CROSSING_SIN:
        return None
    offset = centre - start
    t = (offset[0] * axis[1] - offset[1] * axis[0]) / cross
    return start + direction * t if 0.0 <= t <= 1.5 * reach else None

"""
source_extract.diagrams.detection.junction_detector — Junctions and crossings of the drawn lines (node candidates).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from source_extract.diagrams.detection.skeletonizer import skeletonize
from source_extract.diagrams.models.line_scale import LineScale

_OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_MIN_COMPONENT_PX = 60
_SPUR_PX = 10.0
_MERGE_PX = 10.0
_SMALL_HOLE_PX2 = 30
_MAX_HALF_WIDTH_PX = 12.0
_GROUP_PX = 2


def detect_junctions(
    mask: np.ndarray,
    min_component_px: int | None = None,
    spur_px: float | None = None,
    spur_width_factor: float = 2.5,
    merge_px: float | None = None,
    scale: LineScale | None = None,
) -> list[tuple[float, float]]:
    """Pixels ``(x, y)`` where three or more line branches meet.

    Components smaller than ``min_component_px`` (default 60 px; text, isolated
    dashes) are dropped. A skeleton branch ending freely within ``spur_px``
    (default 10 px) + factor × local half width of a junction is a spur
    (arrowhead, letter touching a line, stroke corner) and is removed before
    junctions are counted. Junctions closer than ``merge_px`` (default 10 px)
    are merged. Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    min_component_px = s.count(_MIN_COMPONENT_PX) if min_component_px is None else min_component_px
    spur_px = s.length(_SPUR_PX) if spur_px is None else spur_px
    merge_px = s.length(_MERGE_PX) if merge_px is None else merge_px
    lines = _drop_small_components(mask, min_component_px)
    lines = _fill_small_holes(lines, s.area(_SMALL_HOLE_PX2))
    distance = ndimage.distance_transform_edt(lines)
    skeleton = _prune_spurs(skeletonize(lines), distance, spur_px, spur_width_factor, s.length(_MAX_HALF_WIDTH_PX))
    return _merge(_junction_centres(skeleton, s.count(_GROUP_PX)), merge_px)


def _drop_small_components(mask: np.ndarray, min_px: int) -> np.ndarray:
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3), bool))
    keep = np.zeros(labels.max() + 1, bool)
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is not None and max(box[0].stop - box[0].start, box[1].stop - box[1].start) >= min_px:
            keep[index] = True
    return keep[labels]


def _fill_small_holes(mask: np.ndarray, max_area: float) -> np.ndarray:
    holes = ndimage.binary_fill_holes(mask) & ~mask
    labels, count = ndimage.label(holes)
    if count == 0:
        return mask
    sizes = ndimage.sum(holes, labels, index=np.arange(1, count + 1))
    small = np.concatenate([[False], sizes <= max_area])
    return mask | small[labels]


def _neighbourhood(skeleton: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Neighbour count and 0→1 transitions around each pixel (8-neighbourhood)."""
    image = np.pad(skeleton.astype(np.int16), 1)
    ring = [image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:], image[2:, 2:],
            image[2:, 1:-1], image[2:, :-2], image[1:-1, :-2], image[:-2, :-2]]
    count = sum(ring)
    ring.append(ring[0])
    transitions = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.int16) for i in range(8))
    return count, transitions


def _prune_spurs(skeleton: np.ndarray, distance: np.ndarray, spur_px: float, factor: float, max_half_width: float,
                 rounds: int = 3) -> np.ndarray:
    sk = skeleton.copy()
    height, width = sk.shape
    max_steps = int(spur_px + factor * max_half_width)
    for _ in range(rounds):
        count, transitions = _neighbourhood(sk)
        junction = sk & (transitions >= 3)
        removed = False
        for y0, x0 in np.argwhere(sk & (count == 1)):
            if not sk[y0, x0]:
                continue
            parent: dict[tuple[int, int], tuple[int, int] | None] = {(y0, x0): None}
            frontier = [(y0, x0)]
            found = None
            steps = 0
            while frontier and found is None and steps < max_steps:
                steps += 1
                following = []
                for y, x in frontier:
                    for dy, dx in _OFFSETS:
                        q = (y + dy, x + dx)
                        if 0 <= q[0] < height and 0 <= q[1] < width and sk[q] and q not in parent:
                            parent[q] = (y, x)
                            if junction[q]:
                                found = q
                                break
                            following.append(q)
                    if found is not None:
                        break
                frontier = following
            if found is None or steps >= spur_px + factor * min(distance[found], max_half_width):
                continue
            node = parent[found]
            while node is not None:
                sk[node] = False
                node = parent[node]
            removed = True
        if not removed:
            break
    return sk


def _junction_centres(skeleton: np.ndarray, group_px: int) -> list[tuple[float, float]]:
    _, transitions = _neighbourhood(skeleton)
    junction = skeleton & (transitions >= 3)
    labels, count = ndimage.label(ndimage.binary_dilation(junction, iterations=group_px))
    if count == 0:
        return []
    centres = ndimage.center_of_mass(junction, labels * junction, index=np.arange(1, count + 1))
    return [(float(x), float(y)) for y, x in centres]


def _merge(points: list[tuple[float, float]], merge_px: float) -> list[tuple[float, float]]:
    groups: list[list[tuple[float, float]]] = []
    for point in sorted(points):
        for group in groups:
            gx = sum(p[0] for p in group) / len(group)
            gy = sum(p[1] for p in group) / len(group)
            if (point[0] - gx) ** 2 + (point[1] - gy) ** 2 <= merge_px ** 2:
                group.append(point)
                break
        else:
            groups.append([point])
    return [(sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)) for g in groups]

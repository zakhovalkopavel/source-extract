"""
source_extract.diagrams.detection.skeleton_branches — Simple paths of a one-pixel skeleton between its ends and junctions.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

_EIGHT = np.ones((3, 3), bool)
_STEPS = ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))


def skeleton_branches(skeleton: np.ndarray, min_pixels: int = 2, spur_pixels: int = 0,
                      rounds: int = 3) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
    """Branches of ``skeleton`` as ``(N, 2)`` arrays of ``(x, y)`` pixels in walking order, and per branch
    the junction cluster at its first and last pixel (0 = none: a free end or a closed loop).

    Junction pixels (three or more branches leaving them: 0 → 1 changes around the pixel) and their
    skeleton neighbours (else the arms stay diagonally connected) are grouped into clusters and belong to no
    branch; a branch is a connected run of the other pixels, walked from one of its ends (a pixel
    with at most one neighbour in the run). Spurs — branches of at most ``spur_pixels`` from a
    junction to a free end (bumps of the stroke) — are removed and the skeleton split again, up to
    ``rounds`` times. Runs shorter than ``min_pixels`` are dropped.
    """
    sk = skeleton.astype(bool).copy()
    for _ in range(rounds if spur_pixels > 0 else 0):
        branches, ends, paths = _split(sk)
        spurs = [path for path, (first, last) in zip(paths, ends)
                 if len(path) <= spur_pixels and (first == 0) != (last == 0)]
        if not spurs:
            break
        core = sk & (_transitions(sk) >= 3)
        removed = np.zeros_like(sk)
        for path in spurs:
            for y, x in path:
                removed[y, x] = True
        sk &= ~(removed | (ndimage.binary_dilation(removed, structure=_EIGHT) & sk & ~core))
    branches, ends, _ = _split(sk)
    keep = [k for k, b in enumerate(branches) if len(b) >= min_pixels]
    return [branches[k] for k in keep], [ends[k] for k in keep]


def _split(sk: np.ndarray) -> tuple[list[np.ndarray], list[tuple[int, int]], list[list[tuple[int, int]]]]:
    junction = sk & ndimage.binary_dilation(sk & (_transitions(sk) >= 3), structure=_EIGHT)
    clusters, _ = ndimage.label(junction, structure=_EIGHT)
    runs, _ = ndimage.label(sk & ~junction, structure=_EIGHT)
    height, width = sk.shape
    branches: list[np.ndarray] = []
    ends: list[tuple[int, int]] = []
    paths: list[list[tuple[int, int]]] = []
    for index, box in enumerate(ndimage.find_objects(runs), start=1):
        if box is None:
            continue
        ys, xs = np.nonzero(runs[box] == index)
        pixels = {(int(y) + box[0].start, int(x) + box[1].start) for y, x in zip(ys, xs)}
        path = _walk(pixels)
        paths.append(path)
        branches.append(np.array([(x, y) for y, x in path], float))
        ends.append((_cluster_at(clusters, path[0], height, width), _cluster_at(clusters, path[-1], height, width)))
    return branches, ends, paths


def _transitions(sk: np.ndarray) -> np.ndarray:
    """0 → 1 changes around each pixel (8-neighbourhood in circular order): the number of branches leaving it."""
    image = np.pad(sk.astype(np.int16), 1)
    ring = [image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:], image[2:, 2:],
            image[2:, 1:-1], image[2:, :-2], image[1:-1, :-2], image[:-2, :-2]]
    ring.append(ring[0])
    return sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.int16) for i in range(8))


def _walk(pixels: set[tuple[int, int]]) -> list[tuple[int, int]]:
    def around(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in _STEPS if (p[0] + dy, p[1] + dx) in pixels]

    start = min((p for p in pixels if len(around(p)) <= 1), default=min(pixels))
    path, seen = [start], {start}
    while True:
        following = [q for q in around(path[-1]) if q not in seen]
        if not following:
            return path
        path.append(following[0])
        seen.add(following[0])


def _cluster_at(clusters: np.ndarray, pixel: tuple[int, int], height: int, width: int) -> int:
    y, x = pixel
    window = clusters[max(y - 1, 0):min(y + 2, height), max(x - 1, 0):min(x + 2, width)]
    found = window[window > 0]
    return int(found[0]) if found.size else 0

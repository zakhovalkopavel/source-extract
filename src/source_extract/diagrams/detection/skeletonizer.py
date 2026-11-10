"""
source_extract.diagrams.detection.skeletonizer — One-pixel centre lines of an ink mask (Zhang–Suen thinning).
"""
from __future__ import annotations

import numpy as np


def skeletonize(mask: np.ndarray) -> np.ndarray:
    """Thin ``mask`` to 8-connected centre lines; topology (junctions, loops) is kept."""
    image = np.pad(mask.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:]
            p5, p6, p7 = image[2:, 2:], image[2:, 1:-1], image[2:, :-2]
            p8, p9 = image[1:-1, :-2], image[:-2, :-2]
            ring = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            count = sum(n.astype(np.int16) for n in ring[:8])
            transitions = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.int16) for i in range(8))
            if step == 0:
                first, second = p2 * p4 * p6, p4 * p6 * p8
            else:
                first, second = p2 * p4 * p8, p2 * p6 * p8
            centre = image[1:-1, 1:-1]
            remove = (centre == 1) & (count >= 2) & (count <= 6) & (transitions == 1) & (first == 0) & (second == 0)
            if remove.any():
                centre[remove] = 0
                changed = True
    return image[1:-1, 1:-1].astype(bool)

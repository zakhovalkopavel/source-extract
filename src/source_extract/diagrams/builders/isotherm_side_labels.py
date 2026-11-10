"""
source_extract.diagrams.builders.isotherm_side_labels — Isotherm temperatures printed beside a line (joined to it by a short leader, or touching it), from the words read on the page.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.page_word import PageWord

_REACH_PX = 80.0
_LEADER_GAP_PX = 3
_LEADER_SIDE_PX = 1
_TOUCH_PX = 6.0
_ALONE_PX = 15.0


def side_label_pieces(
    words: list[tuple[float, PageWord]],
    pieces: list[np.ndarray],
    mask: np.ndarray,
    scale: LineScale | None = None,
) -> list[tuple[int, float, PageWord]]:
    """Piece labelled by each word: ``words`` (temperature, word), ``pieces`` page pixel paths (N, 2), ``mask``
    the page ink.

    A piece running into the word box is labelled by it. Else pieces up to 80 px from the box are
    candidates; a piece is joined to the box when a straight
    segment from the box to one of its pixels (within 6 px of its nearest) has ink within ±1 px all along,
    with no gap over 3 px, except gaps up to 6 px starting within 15 px of the box (a leader may stop
    short of the word, and a glyph may be lost from the word).
    The farthest joined piece over 15 px away is labelled (a leader, which may cross nearer lines on its
    way); else the nearest joined one; without ink, the nearest one when it touches the box (≤ 6 px) and
    no other piece is within 15 px. Returns (piece index, temperature, word). Pixel sizes are for the
    reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    reach, touch, alone = s.length(_REACH_PX), s.length(_TOUCH_PX), s.length(_ALONE_PX)
    side, max_gap = s.count(_LEADER_SIDE_PX), s.count(_LEADER_GAP_PX)
    found = []
    if not words:
        return found
    inked = ndimage.binary_dilation(mask, structure=np.ones((2 * side + 1, 2 * side + 1), bool))
    for value, word in words:
        near = []
        for k, pixels in enumerate(pieces):
            gap = _joined(inked, word.box, pixels, reach, touch, alone)
            if gap is not None:
                near.append((gap[0], k, gap[1]))
        if not near:
            continue
        near.sort(key=lambda item: item[0])
        joined = [(distance, k) for distance, k, gap in near if gap <= max_gap]
        leaders = [k for distance, k in joined if distance > alone]
        if near[0][0] < 0.5:
            chosen = near[0][1]
        else:
            chosen = leaders[-1] if leaders else (joined[0][1] if joined else None)
        if chosen is None and near[0][0] <= touch and (len(near) == 1 or near[1][0] > alone):
            chosen = near[0][1]
        if chosen is not None:
            found.append((chosen, value, word))
    return found


def _joined(inked: np.ndarray, box: tuple[int, int, int, int], pixels: np.ndarray, reach: float,
            slack: float, zone: float) -> tuple[float, int] | None:
    """Distance from the box to the path (None beyond ``reach``), and the smallest longest gap of the
    segments from the box to the path pixels within ``slack`` of that distance (a leader need not hit the
    nearest pixel)."""
    clamped = np.column_stack([np.clip(pixels[:, 0], box[0], box[2]), np.clip(pixels[:, 1], box[1], box[3])])
    distances = np.linalg.norm(pixels - clamped, axis=1)
    nearest = float(distances.min())
    if nearest > reach:
        return None
    close = np.flatnonzero(distances <= nearest + slack)
    return nearest, min(_gap(inked, clamped[k], pixels[k], slack, zone) for k in close)


def _gap(inked: np.ndarray, a: np.ndarray, b: np.ndarray, lead: float, zone: float) -> int:
    """Longest run of points (1 px apart) of the segment a → b off the (dilated) ink, not counting runs of
    up to ``lead`` points starting within ``zone`` of ``a`` (a leader may stop short of the word, which
    may have lost a glyph)."""
    length = float(np.linalg.norm(b - a))
    if length < 1.0:
        return 0
    points = (a + np.outer(np.linspace(0.0, 1.0, int(length) + 1), b - a)).round().astype(int)
    x = np.clip(points[:, 0], 0, inked.shape[1] - 1)
    y = np.clip(points[:, 1], 0, inked.shape[0] - 1)
    off = ~inked[y, x]
    if not off.any():
        return 0
    edges = np.flatnonzero(np.diff(np.concatenate(([0], off.astype(np.int8), [0]))))
    starts, runs = edges[::2], edges[1::2] - edges[::2]
    counted = runs[(starts > zone) | (runs > lead)]
    return int(counted.max()) if len(counted) else 0

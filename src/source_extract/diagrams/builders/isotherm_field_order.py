"""
source_extract.diagrams.builders.isotherm_field_order — Order of the isotherm lines across a field: neighbouring lines along sections normal to each line.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from source_extract.diagrams.models.line_scale import LineScale

_FRACTIONS = (0.3, 0.5, 0.7)
_DIRECTION_PX = 8
_REACH_PX = 400.0
_LINE_PX = 3
_START_PX = 2.0
_SPACING_RATIO = 1.8


def field_order_chains(
    pieces: list[np.ndarray],
    groups: list[int],
    stop: np.ndarray,
    scale: LineScale | None = None,
) -> list[list[int]]:
    """Groups of neighbouring isotherm lines, in order across a field.

    ``pieces``: pixel paths (N, 2) in the coordinates of ``stop`` (True where a section ends: the
    boundaries, the triangle frame, outside the triangle); ``groups[i]``: the line group of piece ``i``.
    From 30 %, 50 % and 70 % along each piece a section runs both ways along its normal, up to 400 px or
    a stop, listing the pieces it meets in order. A section is cut where a piece repeats and where the
    spacing between two met lines is more than 1.8 × the median spacing of the section (a line missed in
    between). Sections of at least two lines, as lists of groups (no group twice), are returned once
    each. Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    height, width = stop.shape
    raster = Image.new("I", (width, height), 0)
    draw = ImageDraw.Draw(raster)
    for i, pixels in enumerate(pieces):
        if len(pixels) >= 2:
            draw.line([tuple(p) for p in pixels], fill=i + 1, width=s.count(_LINE_PX))
    owner = np.array(raster, np.int32)
    reach, start = s.length(_REACH_PX), s.length(_START_PX)
    step = s.count(_DIRECTION_PX)
    chains: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for i, pixels in enumerate(pieces):
        if len(pixels) < 2 * step + 1:
            continue
        for fraction in _FRACTIONS:
            k = min(max(int(fraction * (len(pixels) - 1)), step), len(pixels) - 1 - step)
            tangent = pixels[k + step] - pixels[k - step]
            norm = float(np.linalg.norm(tangent))
            if norm == 0:
                continue
            normal = np.array([-tangent[1], tangent[0]]) / norm
            sides = [_walk(owner, stop, pixels[k], sign * normal, i, start, reach) for sign in (-1.0, 1.0)]
            met = [(-t, j) for t, j in reversed(sides[0])] + [(0.0, i)] + sides[1]
            section = _cut(met, i)
            chain = [groups[j] for _, j in section]
            if len(chain) >= 2 and len(set(chain)) == len(chain):
                key = tuple(chain) if chain[0] < chain[-1] else tuple(reversed(chain))
                if key not in seen:
                    seen.add(key)
                    chains.append(list(key))
    return chains


def _walk(owner: np.ndarray, stop: np.ndarray, p: np.ndarray, u: np.ndarray, own: int,
          start: float, reach: float) -> list[tuple[float, int]]:
    """Pieces met along ``p + t·u`` (``start`` ≤ t ≤ ``reach``) before a stop: (t, piece) at the first pixel of each."""
    height, width = stop.shape
    met: list[tuple[float, int]] = []
    current = own
    t = start
    while t <= reach:
        x, y = int(round(p[0] + t * u[0])), int(round(p[1] + t * u[1]))
        if not (0 <= x < width and 0 <= y < height) or stop[y, x]:
            break
        value = int(owner[y, x]) - 1
        if value >= 0 and value != current:
            met.append((t, value))
        if value >= 0:
            current = value
        t += 1.0
    return met


def _cut(met: list[tuple[float, int]], own: int) -> list[tuple[float, int]]:
    """The run of ``met`` (position, piece; ordered) around ``own`` without a repeated piece or a wide spacing."""
    at = next(k for k, (t, j) in enumerate(met) if j == own and t == 0.0)
    lo, hi = at, at
    pieces = {own}
    while lo > 0 and met[lo - 1][1] not in pieces:
        lo -= 1
        pieces.add(met[lo][1])
    while hi < len(met) - 1 and met[hi + 1][1] not in pieces:
        hi += 1
        pieces.add(met[hi][1])
    run = met[lo:hi + 1]
    if len(run) < 3:
        return run
    gaps = np.diff([t for t, _ in run])
    limit = _SPACING_RATIO * float(np.median(gaps))
    first, last = 0, len(run) - 1
    own_at = at - lo
    for k, gap in enumerate(gaps):
        if gap > limit:
            if k < own_at:
                first = k + 1
            elif last == len(run) - 1:
                last = k
    return run[first:last + 1]

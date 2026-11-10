"""
source_extract.diagrams.detection.tick_matcher — Pair detected tick pixels with the config tick values.
"""
from __future__ import annotations

import numpy as np


def match_ticks(
    candidates: list[float],
    values: list[float],
    frame_ends: tuple[float, float] | None = None,
    anchors: list[tuple[float, float]] | None = None,
) -> tuple[list[float | None], list[float]]:
    """Pixel for each value (``None`` = unmatched) and residuals against a straight-line fit.

    Values are listed in the order of increasing pixels (left to right, top to
    bottom). Every pair of candidates is tried as two consecutive values. Order:
    most matched values; then most ``anchors`` agreeing within half a tick
    spacing (approximate ``(value, pixel)`` pairs from labelled invariant seeds,
    which resolves evenly spaced ticks shifted by one); then only spacings
    ≥ 75 % of the widest remain (minor ticks between listed values are skipped);
    then the smallest mean error. ``frame_ends`` (the frame line positions at
    both ends of the edge) are added as candidates so the frame can stand in
    for outer ticks.
    """
    pool = sorted(set(round(c, 2) for c in candidates) | set(round(c, 2) for c in (frame_ends or ())))
    cands = np.array(pool, float)
    vals = np.array(values, float)
    if len(cands) < 2:
        return [None] * len(values), []
    diffs = np.abs(np.diff(vals))
    hypotheses = []
    for i in range(len(vals) - 1):
        dv = vals[i + 1] - vals[i]
        if dv == 0:
            continue
        for a_index in range(len(cands)):
            for b_index in range(a_index + 1, len(cands)):
                scale = (cands[b_index] - cands[a_index]) / dv
                offset = cands[a_index] - scale * vals[i]
                predicted = offset + scale * vals
                spacing = abs(scale) * float(np.median(diffs))
                tolerance = max(3.0, 0.05 * spacing)
                distance = np.abs(predicted[:, None] - cands[None, :])
                nearest = distance.argmin(axis=1)
                error = distance[np.arange(len(vals)), nearest]
                matched = error <= tolerance
                if matched.sum() < 2:
                    continue
                agreeing = sum(
                    1 for value, pixel in (anchors or ())
                    if abs(offset + scale * value - pixel) <= 0.5 * spacing
                )
                hypotheses.append((int(matched.sum()), abs(scale), float(error[matched].mean()), nearest, matched, agreeing))
    if not hypotheses:
        return [None] * len(values), []
    best_count = max(h[0] for h in hypotheses)
    top = [h for h in hypotheses if h[0] == best_count]
    best_agreeing = max(h[5] for h in top)
    top = [h for h in top if h[5] == best_agreeing]
    max_scale = max(h[1] for h in top)
    top = [h for h in top if h[1] >= 0.75 * max_scale]
    _, _, _, nearest, matched, _ = min(top, key=lambda h: h[2])
    pixels: list[float | None] = [float(cands[n]) if m else None for n, m in zip(nearest, matched)]
    used = [p for p in pixels if p is not None]
    if len(set(used)) != len(used):
        seen: set[float] = set()
        for index, pixel in enumerate(pixels):
            if pixel is None:
                continue
            if pixel in seen:
                pixels[index] = None
            seen.add(pixel)
    pairs = [(v, p) for v, p in zip(values, pixels) if p is not None]
    if len(pairs) < 2:
        return pixels, []
    fit = np.polyfit([v for v, _ in pairs], [p for _, p in pairs], 1)
    residuals = [float(p - np.polyval(fit, v)) for v, p in pairs]
    return pixels, residuals

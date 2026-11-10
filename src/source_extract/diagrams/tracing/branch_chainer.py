"""
source_extract.diagrams.tracing.branch_chainer — Join skeleton branches into drawn lines (through crossings, breaks, dash gaps and labels).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree

from source_extract.diagrams.models.branch_chain import BranchChain
from source_extract.diagrams.models.line_scale import LineScale

_DIRECTION_PX = 8
_CROSSING_DEG = 40.0
_INK_GAP_PX = 14.0
_DASH_GAP_PX = 30.0
_DASH_MAX_PX = 70.0
_TEXT_GAP_PX = 130.0
_TEXT_SHARE = 0.3
_LATERAL_PX = 6.0
_LATERAL_SHARE = 0.25
_SAMPLE_PX = 2.0


def chain_branches(
    branches: list[np.ndarray],
    junctions: list[tuple[int, int]],
    text: np.ndarray,
    barrier: np.ndarray,
    scale: LineScale | None = None,
) -> list[BranchChain]:
    """Drawn lines from skeleton ``branches`` (``skeleton_branches`` output, page-local pixels).

    At a junction cluster the two branch ends pointing most nearly in opposite directions
    (within 40°) continue each other (a line crossed by a leader or touched by a tick).
    A free end continues across a gap to another free end when each lies ahead of the other
    (within 6 px or a quarter of the gap of the other's direction) and the gap does not touch
    ``barrier`` (boundary curves, the frame): up to 14 px (a break in the stroke), up to 30 px
    when one side is a dash (≤ 70 px), up to 130 px when ≥ 30 % of the gap lies on ``text``
    (a label printed in the line). Cheapest joins first (gap / 130 px + 1 − cos of both
    directions); each end joins once. Directions are taken over the last 8 px of a branch.
    Pixel sizes are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    step = s.count(_DIRECTION_PX)
    lengths = [_length(b) for b in branches]
    points, directions = [], []
    for branch in branches:
        for end in (0, 1):
            p, u = _end(branch, end, step)
            points.append(p)
            directions.append(u)
    linked: dict[int, tuple[int, str]] = {}

    by_cluster: dict[int, list[int]] = {}
    for b, (first, last) in enumerate(junctions):
        for end, cluster in ((0, first), (1, last)):
            if cluster:
                by_cluster.setdefault(cluster, []).append(2 * b + end)
    limit = math.cos(math.radians(180.0 - _CROSSING_DEG))
    for members in by_cluster.values():
        pairs = sorted((float(directions[i] @ directions[j]), i, j)
                       for k, i in enumerate(members) for j in members[k + 1:] if i // 2 != j // 2)
        for cosine, i, j in pairs:
            if cosine <= limit and i not in linked and j not in linked:
                linked[i], linked[j] = (j, "junction"), (i, "junction")

    free = [i for i in range(len(points)) if i not in linked and not junctions[i // 2][i % 2]]
    if free:
        tree = cKDTree(np.array([points[i] for i in free]))
        options = []
        for a, b in tree.query_pairs(r=s.length(_TEXT_GAP_PX)):
            i, j = free[a], free[b]
            if i // 2 == j // 2:
                continue
            kind = _gap_kind(points[i], directions[i], points[j], directions[j], lengths[i // 2], lengths[j // 2],
                             text, barrier, s)
            if kind is None:
                continue
            gap = float(np.linalg.norm(points[j] - points[i]))
            v = (points[j] - points[i]) / max(gap, 1e-9)
            cost = gap / s.length(_TEXT_GAP_PX) + (1.0 - float(directions[i] @ v)) + (1.0 - float(-directions[j] @ v))
            options.append((cost, i, j, kind))
        for _, i, j, kind in sorted(options):
            if i not in linked and j not in linked:
                linked[i], linked[j] = (j, kind), (i, kind)
    return _assemble(branches, lengths, linked)


def _length(branch: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(branch, axis=0), axis=1).sum()) if len(branch) > 1 else 0.0


def _end(branch: np.ndarray, end: int, step: int) -> tuple[np.ndarray, np.ndarray]:
    """End pixel and outward unit direction of ``branch`` at its first (0) or last (1) pixel."""
    k = min(step, len(branch) - 1)
    p = branch[0] if end == 0 else branch[-1]
    q = branch[k] if end == 0 else branch[-1 - k]
    u = p - q
    norm = float(np.linalg.norm(u))
    return p.astype(float), (u / norm if norm > 0 else np.zeros(2))


def _gap_kind(p1, u1, p2, u2, length1, length2, text, barrier, s: LineScale) -> str | None:
    delta = p2 - p1
    gap = float(np.linalg.norm(delta))
    if gap == 0:
        return "ink"
    lateral = max(s.length(_LATERAL_PX), _LATERAL_SHARE * gap)
    for p, u, q in ((p1, u1, p2), (p2, u2, p1)):
        d = q - p
        if float(u @ d) <= 0 or abs(float(u[0] * d[1] - u[1] * d[0])) > lateral:
            return None
    n = max(2, int(gap / _SAMPLE_PX))
    samples = np.round(p1 + np.linspace(0.0, 1.0, n)[:, None] * delta).astype(int)
    inside = (samples[:, 1] >= 0) & (samples[:, 1] < text.shape[0]) & (samples[:, 0] >= 0) & (samples[:, 0] < text.shape[1])
    samples = samples[inside]
    if barrier[samples[:, 1], samples[:, 0]].any():
        return None
    if gap <= s.length(_INK_GAP_PX):
        return "ink"
    if gap <= s.length(_DASH_GAP_PX) and min(length1, length2) <= s.length(_DASH_MAX_PX):
        return "dash"
    if text[samples[:, 1], samples[:, 0]].mean() >= _TEXT_SHARE:
        return "text"
    return None


def _assemble(branches: list[np.ndarray], lengths: list[float], linked: dict[int, tuple[int, str]]) -> list[BranchChain]:
    seen: set[int] = set()
    chains: list[BranchChain] = []

    def walk(start_end: int) -> BranchChain:
        pixels: list[np.ndarray] = []
        gaps: list[tuple[int, str]] = []
        ink = gap = 0.0
        end = start_end
        closed = False
        while True:
            b = end // 2
            seen.add(b)
            part = branches[b] if end % 2 == 0 else branches[b][::-1]
            if pixels:
                previous = pixels[-1][-1]
                total = sum(len(p) for p in pixels)
                jump = float(np.linalg.norm(part[0] - previous))
                gap += jump
                kind = linked[end][1]
                if kind != "junction":
                    gaps.append((total, kind))
            pixels.append(part)
            ink += lengths[b]
            out = end ^ 1
            if out not in linked:
                break
            nxt = linked[out][0]
            if nxt // 2 in seen:
                closed = nxt == start_end
                break
            end = nxt
        return BranchChain(np.concatenate(pixels), gaps, ink, gap, closed)

    for b in range(len(branches)):
        for end in (2 * b, 2 * b + 1):
            if b not in seen and end not in linked:
                chains.append(walk(end))
    for b in range(len(branches)):
        if b not in seen:
            chains.append(walk(2 * b))
    return chains

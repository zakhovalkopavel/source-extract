"""
source_extract.diagrams.builders.node_temperature_reader — Printed temperatures of the curve nodes (invariant points, edge points) and of points along the curves (saddles), from the words read on the page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from source_extract.diagrams.models.boundary_graph import BoundaryNode
from source_extract.diagrams.models.line_scale import LineScale
from source_extract.diagrams.models.page_word import PageWord

_NUMBER = re.compile(r"^~?(\d{1,4})[.,]?(\d{0,3})[.,]?$")
_RANGE_C = (300.0, 3000.0)
_REACH_PX = 100.0
_ROUND_PENALTY_PX = 80.0
_NEAREST_SLACK_PX = 20.0
_NO_PAIR = 1e9
_CURVE_REACH_PX = 45.0
_CURVE_END_PX = 10.0
_FORMULA = re.compile(r"[A-Z][a-z0-9]")
_NAME = re.compile(r"[a-z]{4}")
_FORMULA_GAP = 0.8


@dataclass(frozen=True)
class CurveTemperature:
    """Printed temperature of a point inside a curve: graph edge ``edge``, pixel ``index`` of its path."""

    edge: int
    index: int
    value: float
    word: PageWord


def printed_temperature(text: str) -> float | None:
    """°C of a word that is a printed temperature (3–4 digits, optional leading ``~``, a stray ``.`` or ``,``
    read between or after the digits; 300–3000), else None."""
    match = _NUMBER.match(text.strip())
    if match is None:
        return None
    digits = match.group(1) + match.group(2)
    if not 3 <= len(digits) <= 4:
        return None
    value = float(digits)
    return value if _RANGE_C[0] <= value <= _RANGE_C[1] else None


def read_node_temperatures(
    nodes: list[BoundaryNode],
    words: list[PageWord],
    step_C: float = 100.0,
    scale: LineScale | None = None,
) -> dict[int, tuple[float, PageWord]]:
    """Temperature and word of each ``junction`` or ``edge`` node that has a printed temperature next to it.

    A word is a temperature by ``printed_temperature``; its distance to a node is the distance to its box,
    up to 100 px. A word goes only to nodes at most 20 px farther than its nearest node (a label belongs to
    the point it is printed at). The cost of a pair is the distance plus 80 px for a multiple of ``step_C``
    (isotherm labels are round, invariant temperatures rarely); words and nodes are paired one to one with
    the least total cost, a node without a word costing 100 px. Pixel sizes are for the reference line
    width, scaled by ``scale``.
    """
    s = scale or LineScale()
    reach = s.length(_REACH_PX)
    candidates = [n for n, node in enumerate(nodes) if node.kind in ("junction", "edge")]
    readings = [(w, value) for w, word in enumerate(words) if (value := printed_temperature(word.text)) is not None]
    if not candidates or not readings:
        return {}
    cost = np.full((len(candidates), len(readings) + len(candidates)), _NO_PAIR)
    cost[:, len(readings):][np.diag_indices(len(candidates))] = reach
    for j, (w, value) in enumerate(readings):
        distances = np.array([words[w].distance(nodes[n].pixel) for n in candidates])
        limit = distances.min() + s.length(_NEAREST_SLACK_PX)
        for i, distance in enumerate(distances):
            if distance <= reach and distance <= limit:
                cost[i, j] = distance + (s.length(_ROUND_PENALTY_PX) if value % step_C == 0 else 0.0)
    found: dict[int, tuple[float, PageWord]] = {}
    for i, j in zip(*linear_sum_assignment(cost)):
        if j < len(readings) and cost[i, j] < _NO_PAIR:
            w, value = readings[j]
            found[candidates[i]] = (value, words[w])
    return found


def read_curve_temperatures(
    curves: dict[int, np.ndarray],
    words: list[PageWord],
    taken: set[int],
    step_C: float = 100.0,
    scale: LineScale | None = None,
    end_temperatures: dict[int, list[float]] | None = None,
) -> list[CurveTemperature]:
    """Printed temperatures along the curves (maxima of a boundary, saddles): a temperature word not in
    ``taken`` (word indices already given to nodes), not a multiple of ``step_C`` (isotherm labels), within
    45 px of a curve pixel at least 10 px from the curve ends. ``curves``: graph edge index → page pixels
    (N, 2). The word goes to the nearest such pixel; one point per word. ``end_temperatures`` (graph edge
    index → temperatures read at its end nodes): a curve is not offered a value that is not above them,
    since a point inside a boundary with a printed temperature is its maximum. A word printed right under
    a formula (``_under_formula``) is the melting point of that compound, not a curve point. Pixel sizes
    are for the reference line width, scaled by ``scale``.
    """
    s = scale or LineScale()
    reach, margin = s.length(_CURVE_REACH_PX), s.length(_CURVE_END_PX)
    ends = end_temperatures or {}
    found = []
    for w, word in enumerate(words):
        value = printed_temperature(word.text)
        if w in taken or value is None or value % step_C == 0 or _under_formula(word, words):
            continue
        best = None
        for k, pixels in curves.items():
            if len(pixels) < 3 or any(value <= t for t in ends.get(k, [])):
                continue
            steps = np.r_[0.0, np.cumsum(np.hypot(*np.diff(pixels, axis=0).T))]
            inner = np.flatnonzero((steps >= margin) & (steps <= steps[-1] - margin))
            if inner.size == 0:
                continue
            distance = _box_distance(word.box, pixels[inner])
            i = int(np.argmin(distance))
            if distance[i] <= reach and (best is None or distance[i] < best[0]):
                best = (float(distance[i]), k, int(inner[i]))
        if best is not None:
            found.append(CurveTemperature(best[1], best[2], value, word))
    return found


def _under_formula(word: PageWord, words: list[PageWord]) -> bool:
    """A word of a chemical formula (``_FORMULA``: a capital then a lower-case letter or a digit, no 4
    lower-case letters in a row as in a phase name) lies above ``word``, overlapping it across, its bottom
    at most 0.8 × the word's height above it."""
    x0, y0, x1, y1 = word.box
    gap = _FORMULA_GAP * (y1 - y0)
    return any(other is not word and _FORMULA.search(other.text) and not _NAME.search(other.text)
               and other.box[0] < x1 and other.box[2] > x0 and y0 - gap <= other.box[3] <= y0 + gap / 2
               for other in words)


def _box_distance(box: tuple[int, int, int, int], points: np.ndarray) -> np.ndarray:
    dx = np.maximum.reduce([box[0] - points[:, 0], np.zeros(len(points)), points[:, 0] - box[2]])
    dy = np.maximum.reduce([box[1] - points[:, 1], np.zeros(len(points)), points[:, 1] - box[3]])
    return np.hypot(dx, dy)

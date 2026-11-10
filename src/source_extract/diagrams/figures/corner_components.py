"""
source_extract.diagrams.figures.corner_components — Which component is at which triangle corner, from the read corner labels.
"""
from __future__ import annotations

import itertools
from difflib import SequenceMatcher

from source_extract.diagrams.figures.formula_letters import formula_letters

_MIN_SIMILARITY = 0.66


def corner_components(texts: dict[str, str], components: list[str]) -> dict[str, str] | None:
    """``{corner: component}`` for the corners ``top``, ``left``, ``right``, or None when unsure.

    Each line of a corner's text is reduced to its letters (0 read as O, case
    ignored) and compared with each component's letters (a trailing x or n
    dropped: FeOx and FeOn read as FeO, which also matches a printed Fe2O3). A
    line with at least as many letters and similar enough (ratio ≥ 0.66) names
    that component at the corner; text recognition often misreads one letter
    (``Cad`` for CaO) but a shorter fragment (``fo``) is not a label. The assignment with
    the highest total similarity over all orders is used when at least two corners
    are named; the third corner takes the remaining component.
    """
    keys = {c: formula_letters(c) for c in components}
    corners = ("top", "left", "right")
    score = {(corner, c): max((_similarity(line, keys[c]) for line in _lines(texts.get(corner, ""))), default=0.0)
             for corner in corners for c in components}
    best, best_total = None, 0.0
    for order in itertools.permutations(components):
        named = [score[(corner, c)] for corner, c in zip(corners, order) if score[(corner, c)] >= _MIN_SIMILARITY]
        if len(named) >= 2 and sum(named) > best_total:
            best, best_total = dict(zip(corners, order)), sum(named)
    return best


def _lines(text: str) -> list[str]:
    return [letters for letters in (formula_letters(line) for line in text.splitlines()) if len(letters) >= 2]


def _similarity(line: str, key: str) -> float:
    return SequenceMatcher(None, line, key).ratio() if len(line) >= len(key) else 0.0

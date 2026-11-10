"""
source_extract.diagrams.figures.formula_letters — Letters of an oxide formula as text recognition reads it (Fe,0, → feo).
"""
from __future__ import annotations

import re


def formula_letters(text: str) -> str:
    """Lower-case letters of ``text`` with 0 read as O; a trailing x or n is dropped (FeOx, FeOn → feo).

    Text recognition writes subscripts as digits, commas or dots and O as 0
    (``Al,O,``, ``Ca0``, ``Fe,0,``), so formulas are compared by these letters.
    Fe2O3 and FeO therefore both give the letters of FeOx.
    """
    letters = re.sub(r"[^a-z]", "", text.lower().replace("0", "o"))
    return letters[:-1] if len(letters) > 2 and letters[-1] in "xn" else letters

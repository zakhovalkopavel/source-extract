"""
source_extract.diagrams.figures.formula_display — A formula with subscript characters for the console (Fe2O3 → Fe₂O₃).
"""
from __future__ import annotations

import re

_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def display_formula(formula: str) -> str:
    """Digits after an element symbol become subscripts, a trailing x becomes ₓ; leading coefficients stay (2CaO·SiO₂)."""
    text = re.sub(r"(?<=[A-Za-z)])\d+", lambda m: m.group().translate(_SUBSCRIPT), formula)
    return text[:-1] + "ₓ" if text.endswith("x") else text

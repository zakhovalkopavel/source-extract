"""
source_extract.diagrams.figures.formula_molar_mass — Molar mass of an oxide formula from the atomic weights (TiO2 → 79.866).
"""
from __future__ import annotations

import re

from source_extract.diagrams.constants.atomic_mass import ATOMIC_MASS

_FORMULA = re.compile(r"(?:[A-Z][a-z]?\d*)+")


def formula_molar_mass(formula: str) -> float | None:
    """g/mol of ``formula`` (``Al2O3``); None for a formula without a fixed composition (``FeOx``) or an unknown element."""
    if not _FORMULA.fullmatch(formula):
        return None
    total = 0.0
    for element, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
        if element not in ATOMIC_MASS:
            return None
        total += ATOMIC_MASS[element] * (int(count) if count else 1)
    return total

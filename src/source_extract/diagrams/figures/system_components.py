"""
source_extract.diagrams.figures.system_components — Component formulas from a system id (cao-feox-sio2 → CaO, FeOx, SiO2).
"""
from __future__ import annotations

import re

from source_extract.diagrams.constants.atomic_mass import ATOMIC_MASS

_ELEMENTS = set(ATOMIC_MASS)


def system_components(system_id: str) -> list[str]:
    """The formula of each hyphen-separated part, element symbols capitalised; a trailing ``x`` stays (FeOx).

    Two-letter symbols are tried before one-letter ones. Raises ValueError for a
    part that is not a formula of known element symbols.
    """
    out = []
    for part in system_id.split("-"):
        formula, index = "", 0
        while index < len(part):
            pair, single = part[index:index + 2].capitalize(), part[index].upper()
            if pair in _ELEMENTS and len(pair) == 2:
                formula, index = formula + pair, index + 2
            elif single in _ELEMENTS:
                formula, index = formula + single, index + 1
            elif part[index].isdigit() or (part[index] == "x" and index == len(part) - 1 and formula):
                formula, index = formula + part[index], index + 1
            else:
                raise ValueError(f"'{system_id}': '{part}' is not an oxide formula")
        if not re.search(r"[A-Z]", formula):
            raise ValueError(f"'{system_id}': empty component")
        out.append(formula)
    if len(out) != 3:
        raise ValueError(f"'{system_id}': a ternary needs three components, got {len(out)}")
    return out

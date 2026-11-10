"""
source_extract.diagrams.figures.figure_finder — Figures of the caption index that show a given system.
"""
from __future__ import annotations

import re

from source_extract.diagrams.figures.formula_letters import formula_letters

_GROUP = re.compile(r"[a-z]+(?:[\s-]*-[\s-]*[a-z]+)+")
_SEE = re.compile(r"[\s(]*see\s+fig")


def find_system_figures(index: list[dict], components: list[str]) -> list[dict]:
    """Index entries whose caption names a system of exactly these components, in any order.

    Captions and formulas are compared by their letters (``formula_letters``: 0 read
    as O, subscripts and a trailing x or n ignored). A caption part matches when it
    is a run of as many hyphen-joined formulas as components whose letters equal the
    components' letters (so CaO-FeO-Fe2O3-SiO2 is not CaO-FeOx-SiO2) and is not a
    reference to another figure (``base system CaO-SiO2-TiO2 see Fig. 3.264``).
    Entries are returned in index order.
    """
    wanted = {formula_letters(c) for c in components}
    out = []
    for entry in index:
        text = re.sub(r"[\d,.'\"’”“]", "", (entry.get("captionStart") or "").lower().replace("0", "o"))
        for match in _GROUP.finditer(text):
            tokens = [formula_letters(t) for t in re.split(r"[\s-]+", match.group()) if t]
            if len(tokens) == len(components) and set(tokens) == wanted and not _SEE.match(text, match.end()):
                out.append(entry)
                break
    return out

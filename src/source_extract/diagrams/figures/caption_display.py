"""
source_extract.diagrams.figures.caption_display — Readable caption start for choosing a figure (CaO-FeO,-SiO, → CaO-FeOₓ-SiO₂).
"""
from __future__ import annotations

import re

from source_extract.diagrams.figures.formula_display import display_formula
from source_extract.diagrams.figures.formula_letters import formula_letters

_TOKEN = r"[A-Z][A-Za-z0-9,]*"
_GROUP = re.compile(rf"(?<![\w-]){_TOKEN}(?:\s*-\s*{_TOKEN})+")
_RUN = re.compile(r"(?<![\w₀-₉ₓ])\d*[A-Z][A-Za-z0-9,.'’·]*")
_COEFFICIENT = re.compile(r"\d*")
_DOT = re.compile(r"['’·]|,(?=\d+[A-Z])")
_CHARGE = re.compile(r"(?<=[A-Za-z])([1-4]?)\+")
_ZERO_AS_O = re.compile(r"(?<=[A-Z])0|(?<=[A-Z][a-z])0")
_SUPERSCRIPT = str.maketrans("1234+", "¹²³⁴⁺")


def display_caption(
    caption: str,
    components: list[str],
    *,
    extra_formulas: list[str] | tuple[str, ...] | None = None,
) -> str:
    """``caption`` with chemical formulas written with subscripts, for choosing a figure (display only).

    Text recognition writes subscripts as digits, commas or dots, O as 0 and the
    middle dot as ``'``. A hyphen-joined run of as many formulas as components whose
    letters (``formula_letters``) are the components' letters becomes the component
    formulas in the caption's order (``CaO-FeO,-SiO,`` → ``CaO-FeOₓ-SiO₂``). Other
    formulas, with a coefficient and joined by middle dots, are written as the first
    of the components and ``extra_formulas`` whose shape they have, each subscript
    one comma, dot or its own digits (``7Ca0'2Si0,,14Fe,0,,`` → ``7CaO·2SiO₂·14Fe₂O₃,``;
    a comma cannot tell Fe₂O₃ from Fe₃O₄, the earlier one is shown). Charges become
    superscripts (``Fe2+`` → ``Fe²⁺``); elsewhere a 0 after an element symbol reads as O.
    The caption start is cut off mid-text by the index, so the last partial word is
    dropped and ``…`` appended. Captions for the data are read from tiles, not from here.
    Host adapters pass book-specific formula catalogs via ``extra_formulas``.
    """
    by_letters = {formula_letters(c): c for c in components}
    catalog = list(dict.fromkeys([*components, *(extra_formulas or ())]))
    patterns = [(f, _ocr_pattern(f)) for f in catalog]

    def system(match: re.Match) -> str:
        parts = [formula_letters(t) for t in re.split(r"\s*-\s*", match.group())]
        if len(parts) == len(components) and set(parts) == set(by_letters):
            return "-".join(display_formula(by_letters[p]) for p in parts)
        return match.group()

    def formulas(match: re.Match) -> str:
        run, position, out = match.group(), 0, ""
        while True:
            coefficient = _COEFFICIENT.match(run, position).group()
            found = [(m.end(), f) for f, p in patterns if (m := p.match(run, position + len(coefficient)))]
            if not found:
                break
            end = max(e for e, _ in found)
            out += coefficient + display_formula(next(f for e, f in found if e == end))
            position = end
            dot = _DOT.match(run, position)
            if not dot:
                break
            following = _COEFFICIENT.match(run, dot.end()).end()
            if not any(p.match(run, following) for _, p in patterns):
                break
            out, position = out + "·", dot.end()
        return out + run[position:] if out else run

    text = _GROUP.sub(system, " ".join(caption.split()))
    text = _RUN.sub(formulas, text)
    text = _CHARGE.sub(lambda m: (m.group(1) + "+").translate(_SUPERSCRIPT), text)
    text = _ZERO_AS_O.sub("O", text)
    return (text.rsplit(" ", 1)[0] if " " in text else text) + " …"


def _ocr_pattern(formula: str) -> re.Pattern:
    """The formula as recognised: O or 0 for oxygen, the second letter of a symbol in either case (``AL``),
    each subscript its digits or one comma or dot; no letter may follow."""
    parts = []
    for element, digits in re.findall(r"([A-Z][a-z]?)(\d*)", formula.removesuffix("x")):
        if element == "O":
            parts.append("[O0]")
        else:
            parts.append(element[0] + (f"[{element[1]}{element[1].upper()}]" if len(element) == 2 else ""))
        if digits:
            parts.append(f"(?:{digits}|[,.])")
    if formula.endswith("x"):
        parts.append("[xn]")
    return re.compile("".join(parts) + r"(?![a-z])")

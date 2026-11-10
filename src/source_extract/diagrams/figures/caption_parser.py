"""
source_extract.diagrams.figures.caption_parser — Figure captions and labels in the OCR text of one source page.
"""
from __future__ import annotations

import re

_NUMBER = r"3\.\d+"
_HEAD = re.compile(
    rf"^[^\w\n]{{0,3}}(?:Figs?\.?|Figures?)\s?(?P<numbers>{_NUMBER}(?:\s*(?:and|to|,|-|–|—)\s*{_NUMBER})*)\s*[.,](?P<rest>[^\n]*)",
    re.M,
)
_SPLIT = re.compile(rf"({_NUMBER})|(\bto\b|-|–|—)")
_CAPTION_CHARS = 160


def parse_figure_captions(text: str) -> list[dict]:
    """``{figure, captionStart}`` per figure, in page order.

    A caption starts a line with ``Fig.``/``Figs.``/``Figure(s)``, one or more
    figure numbers (``3.64 and 3.65``, ``3.188 to 3.190``) and ``.`` or ``,``
    (OCR reads some full stops as commas). Text after it on the same line makes
    it a caption; without text it is a label under a drawing, recorded with an
    empty ``captionStart`` unless a caption on the page names the same figure.
    Cross-references (``Fig. 3.251) are ...``) do not match.
    """
    captions: dict[str, str] = {}
    order: list[str] = []
    for match in _HEAD.finditer(text):
        rest = match.group("rest").strip()
        caption = ""
        if rest:
            caption = " ".join(text[match.start("rest"):].split())[:_CAPTION_CHARS]
        for figure in _figures(match.group("numbers")):
            if figure not in captions:
                order.append(figure)
                captions[figure] = caption
            elif caption and not captions[figure]:
                captions[figure] = caption
    return [{"figure": figure, "captionStart": captions[figure]} for figure in order]


def _figures(numbers: str) -> list[str]:
    """``3.188 to 3.190`` → 3.188, 3.189, 3.190; ``3.64 and 3.65`` → 3.64, 3.65."""
    found: list[str] = []
    pending_range = False
    for number, range_word in _SPLIT.findall(numbers):
        if range_word:
            pending_range = True
            continue
        if pending_range and found:
            chapter, first = found[-1].split(".")
            last = int(number.split(".")[1])
            found.extend(f"{chapter}.{n}" for n in range(int(first) + 1, last))
        found.append(number)
        pending_range = False
    return [f"Fig. {n}" for n in found]

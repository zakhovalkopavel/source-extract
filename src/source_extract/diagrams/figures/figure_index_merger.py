"""
source_extract.diagrams.figures.figure_index_merger — Merge a new page range into an existing figure index.
"""
from __future__ import annotations


def merge_figure_index(existing: list[dict], found: list[dict], pages: range) -> list[dict]:
    """Entries of ``existing`` outside ``pages`` plus ``found``, sorted by PDF page and figure number.

    Re-indexing a page range replaces only the entries of those pages.
    """
    kept = [entry for entry in existing if entry["pdfPage"] not in pages]
    return sorted(kept + found, key=_order)


def _order(entry: dict) -> tuple[int, int, int]:
    chapter, number = entry["figure"].removeprefix("Fig. ").split(".")
    return entry["pdfPage"], int(chapter), int(number)

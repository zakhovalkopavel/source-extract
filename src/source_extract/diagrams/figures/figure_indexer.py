"""
source_extract.diagrams.figures.figure_indexer — Caption OCR over a page range → figure index.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image

from source_extract.diagrams.figures.caption_parser import parse_figure_captions
from source_extract.diagrams.rendering.pdf_renderer import render_page


def index_figures(
    pdf_path: Path | str,
    pages: range,
    page_offset: int,
    dpi: int = 150,
    progress: Callable[[int], None] | None = None,
) -> list[dict]:
    """``{figure, pdfPage, printedPage, captionStart}`` for every figure caption or label found by OCR."""
    import pytesseract

    found: list[dict] = []
    for page in pages:
        if progress:
            progress(page)
        image = render_page(pdf_path, page, dpi=dpi)
        text = pytesseract.image_to_string(Image.fromarray(image))
        for caption in parse_figure_captions(text):
            found.append({
                "figure": caption["figure"],
                "pdfPage": page,
                "printedPage": page - page_offset,
                "captionStart": caption["captionStart"],
            })
    return found

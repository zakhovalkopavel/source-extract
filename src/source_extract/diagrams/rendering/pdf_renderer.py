"""source_extract.diagrams.rendering.pdf_renderer — Page → grey image via page-ocr.

``render_page`` accepts PDF, DjVu, or a raster image (see ``page_ocr.render``).
"""
from __future__ import annotations

from page_ocr.render import render_page

__all__ = ["render_page"]

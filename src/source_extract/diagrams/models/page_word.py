"""
source_extract.diagrams.models.page_word — A word read on a page by text recognition.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageWord:
    """``text`` with its Tesseract ``confidence`` (0–100) and ``box`` (x0, y0, x1, y1; page pixels)."""

    text: str
    confidence: float
    box: tuple[int, int, int, int]

    @property
    def centre(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0

    def distance(self, point: tuple[float, float]) -> float:
        """Distance from ``point`` to the box (0 inside)."""
        dx = max(self.box[0] - point[0], 0.0, point[0] - self.box[2])
        dy = max(self.box[1] - point[1], 0.0, point[1] - self.box[3])
        return (dx * dx + dy * dy) ** 0.5

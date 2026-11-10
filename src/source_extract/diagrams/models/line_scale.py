"""
source_extract.diagrams.models.line_scale — Pixel scale of a page, from the width of its drawn lines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class LineScale:
    """Typical line width of a page and the factor that scales pixel tolerances to it.

    Pixel tolerances in the code are written for lines ``REFERENCE_PX`` wide
    (pages rendered at 400 dpi) and scaled by ``factor`` = ``line_px /
    REFERENCE_PX`` rounded to quarters (at least one quarter), so the pages of
    one source, whose line widths differ by a few per cent, share one factor:
    ``length`` for distances, ``count`` for whole pixels (at least 1), ``area``
    for areas. ``source`` tells where ``line_px`` came from (measured, config).
    """

    REFERENCE_PX: ClassVar[float] = 4.25
    STEP: ClassVar[float] = 0.25

    line_px: float = REFERENCE_PX
    source: str = "reference"

    @property
    def factor(self) -> float:
        return max(self.STEP, round(self.line_px / self.REFERENCE_PX / self.STEP) * self.STEP)

    def length(self, reference_px: float) -> float:
        return reference_px * self.factor

    def count(self, reference_px: float) -> int:
        return max(1, round(reference_px * self.factor))

    def area(self, reference_px2: float) -> float:
        return reference_px2 * self.factor ** 2

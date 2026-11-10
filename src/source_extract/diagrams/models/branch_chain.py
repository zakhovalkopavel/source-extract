"""
source_extract.diagrams.models.branch_chain — Skeleton branches joined into one drawn line.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BranchChain:
    """One drawn line: ``pixels`` (``(N, 2)``, x y) in drawing order, ``gaps`` the bridged gaps as
    ``(index, kind)`` (``pixels[index - 1] → pixels[index]`` is not ink; kind ``ink`` a break in
    the stroke, ``dash`` the gap between two dashes, ``text`` a printed label lying in the line),
    ``ink_px`` / ``gap_px`` the lengths on and off ink, ``closed`` for a loop."""

    pixels: np.ndarray
    gaps: list[tuple[int, str]] = field(default_factory=list)
    ink_px: float = 0.0
    gap_px: float = 0.0
    closed: bool = False

    @property
    def length_px(self) -> float:
        return self.ink_px + self.gap_px

    def gap_kinds(self) -> set[str]:
        return {kind for _, kind in self.gaps}

"""
source_extract.diagrams.models.curve_sample — Result of sampling one curve segment on a grid.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CurveSample:
    """Sampled points (start and end = label values) and the grid values left out."""

    points: list[list[float]]
    dropped: list[float] = field(default_factory=list)
    uncovered: list[float] = field(default_factory=list)

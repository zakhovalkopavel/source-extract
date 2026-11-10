"""
source_extract.diagrams.models.ternary_fill — Result of filling the polylines of one ternary file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.models.review_item import ReviewItem
from source_extract.diagrams.models.traced_curve import TracedCurve


@dataclass
class TernaryFill:
    """New file text (only ``polyline_wt`` values changed) plus traces, review and log."""

    text: str
    curves: list[TracedCurve]
    filled: int
    units_missing: bool
    review: list[ReviewItem] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

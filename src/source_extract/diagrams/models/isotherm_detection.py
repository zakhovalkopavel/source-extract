"""
source_extract.diagrams.models.isotherm_detection — Result of the isotherm detector on one ternary page.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.models.detected_isotherm import DetectedIsotherm
from source_extract.diagrams.models.review_item import ReviewItem


@dataclass
class IsothermDetection:
    """``isotherms`` found (one per field piece), ``dropped`` thin lines that are not isotherms as
    ``(page pixels, reason)``, the ``log`` and the ``review`` items."""

    isotherms: list[DetectedIsotherm] = field(default_factory=list)
    dropped: list[tuple[list[tuple[float, float]], str]] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    review: list[ReviewItem] = field(default_factory=list)

"""
source_extract.diagrams.models.binary_extraction — Everything measured for one binary diagram.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.models.calibration_result import CalibrationResult
from source_extract.diagrams.models.measured_line import MeasuredLine
from source_extract.diagrams.models.review_item import ReviewItem
from source_extract.diagrams.models.traced_curve import TracedCurve


@dataclass
class BinaryExtraction:
    """System dict ready to write plus the measurements behind it (overlay, review, log)."""

    system: dict
    calibration: CalibrationResult
    lines: list[MeasuredLine]
    junctions: dict[str, tuple[float, float]]
    curves: list[TracedCurve]
    sampled: list[tuple[float, float]]
    review: list[ReviewItem] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

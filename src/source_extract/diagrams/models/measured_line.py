"""
source_extract.diagrams.models.measured_line — A horizontal invariant line found in the frame.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MeasuredLine:
    """Horizontal stroke: level row (rotation removed), row span, x-extent and temperature."""

    y_level: float
    row_top: float
    row_bottom: float
    x_start: float
    x_end: float
    temperature_C: float

    @property
    def thickness(self) -> float:
        return self.row_bottom - self.row_top + 1

    def to_dict(self) -> dict:
        return {
            "yLevel": round(self.y_level, 1),
            "xExtent": [round(self.x_start, 1), round(self.x_end, 1)],
            "temperature_C": round(self.temperature_C, 1),
        }

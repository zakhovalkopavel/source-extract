"""
source_extract.diagrams.models.binary_calibration — Pixel ↔ (wt%, °C) for a binary diagram.
"""
from __future__ import annotations

from dataclasses import dataclass

from source_extract.diagrams.models.axis_calibration import AxisCalibration


@dataclass
class BinaryCalibration:
    """x and y axis calibrations plus a linear scan-rotation correction.

    x ticks are measured along the bottom frame line (row ``ref_py``), y ticks
    along the left frame line (column ``ref_px``). ``bottom_slope`` is dy/dx of
    the bottom frame line, ``left_slope`` dx/dy of the left frame line.
    """

    x: AxisCalibration
    y: AxisCalibration
    bottom_slope: float
    left_slope: float
    ref_px: float
    ref_py: float

    def level(self, px: float, py: float) -> tuple[float, float]:
        """Pixel projected onto the reference column / row along the frame directions."""
        y_level = py - self.bottom_slope * (px - self.ref_px)
        x_level = px - self.left_slope * (py - self.ref_py)
        return x_level, y_level

    def to_data(self, px: float, py: float) -> tuple[float, float]:
        x_level, y_level = self.level(px, py)
        return self.x.to_value(x_level), self.y.to_value(y_level)

    def to_pixel(self, wt: float, temperature: float) -> tuple[float, float]:
        x_level = self.x.to_pixel(wt)
        y_level = self.y.to_pixel(temperature)
        px, py = x_level, y_level
        for _ in range(5):
            px = x_level + self.left_slope * (py - self.ref_py)
            py = y_level + self.bottom_slope * (px - self.ref_px)
        return px, py

    def rotation_text(self) -> str:
        span = self.x.pixels[-1] - self.x.pixels[0]
        return f"{self.bottom_slope * span:+.1f} px over {span:.0f} px"

    def to_dict(self) -> dict:
        return {
            "x": self.x.to_dict(),
            "y": self.y.to_dict(),
            "bottomSlope": self.bottom_slope,
            "leftSlope": self.left_slope,
            "refPixel": [self.ref_px, self.ref_py],
        }

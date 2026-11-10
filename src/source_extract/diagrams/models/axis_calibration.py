"""
source_extract.diagrams.models.axis_calibration — One plot axis: tick values ↔ tick pixels.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AxisCalibration:
    """Piecewise-linear map between axis values and pixels.

    Ticks may be given in any order; they are sorted by pixel. Beyond the outer
    ticks the outer segments are extended linearly.
    """

    values: list[float]
    pixels: list[float]

    def __post_init__(self) -> None:
        if len(self.values) != len(self.pixels) or len(self.values) < 2:
            raise ValueError("AxisCalibration needs at least two (value, pixel) pairs")
        order = np.argsort(self.pixels)
        self.pixels = [float(self.pixels[i]) for i in order]
        self.values = [float(self.values[i]) for i in order]

    def to_value(self, pixel: float) -> float:
        return float(_interp_extrapolate(pixel, self.pixels, self.values))

    def to_pixel(self, value: float) -> float:
        values, pixels = self.values, self.pixels
        if values[0] > values[-1]:
            values, pixels = values[::-1], pixels[::-1]
        return float(_interp_extrapolate(value, values, pixels))

    def residuals(self) -> list[float]:
        """Tick pixel minus a straight-line fit through all ticks."""
        fit = np.polyfit(self.values, self.pixels, 1)
        return [float(p - np.polyval(fit, v)) for v, p in zip(self.values, self.pixels)]

    def to_dict(self) -> dict:
        return {"values": self.values, "pixels": self.pixels}


def _interp_extrapolate(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
    if x >= xs[-1]:
        return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
    return float(np.interp(x, xs, ys))

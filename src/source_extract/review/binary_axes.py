"""Pixel ↔ (wt% x-component, °C) for binary T–x diagrams.

Mirrors ``source_extract.diagrams.models.binary_calibration.BinaryCalibration``
so the review service does not import the Python extract package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class AxisMap:
    values: tuple[float, ...]
    pixels: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(self.pixels) or len(self.values) < 2:
            raise ValueError("AxisMap needs at least two (value, pixel) pairs")

    def to_value(self, pixel: float) -> float:
        xs = list(self.pixels)
        ys = list(self.values)
        return _interp_extrapolate(pixel, xs, ys)

    def to_pixel(self, value: float) -> float:
        values = list(self.values)
        pixels = list(self.pixels)
        if values[0] > values[-1]:
            values = values[::-1]
            pixels = pixels[::-1]
        return _interp_extrapolate(value, values, pixels)


@dataclass(frozen=True)
class BinaryAxes:
    """Structured binary axes stored under ``digitization.axes``."""

    x_component: str
    other_component: str
    x: AxisMap
    y: AxisMap
    bottom_slope: float
    left_slope: float
    ref_px: float
    ref_py: float

    def level(self, px: float, py: float) -> tuple[float, float]:
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

    def page_bbox(self, *, margin: float = 40.0) -> tuple[int, int, int, int]:
        xs = list(self.x.pixels)
        ys = list(self.y.pixels)
        x0 = int(max(0, min(xs) - margin))
        y0 = int(max(0, min(ys) - margin))
        x1 = int(max(xs) + margin)
        y1 = int(max(ys) + margin)
        return x0, y0, x1, y1

    def to_dict(self) -> dict[str, Any]:
        return {
            "xComponent": self.x_component,
            "otherComponent": self.other_component,
            "x": {"values": list(self.x.values), "pixels": list(self.x.pixels)},
            "y": {"values": list(self.y.values), "pixels": list(self.y.pixels)},
            "bottomSlope": self.bottom_slope,
            "leftSlope": self.left_slope,
            "refPixel": [self.ref_px, self.ref_py],
        }


def is_binary_draft(draft: dict[str, Any] | None) -> bool:
    if not draft:
        return False
    comps = draft.get("components") or []
    if len(comps) == 2:
        return True
    if draft.get("liquidus") and not draft.get("boundaryCurves"):
        return True
    axes = (draft.get("digitization") or {}).get("axes")
    return isinstance(axes, dict) and "x" in axes and "y" in axes


def axes_from_digitization(
    draft: dict[str, Any],
) -> BinaryAxes | None:
    """Build axes from ``digitization.axes`` or by parsing the prose calibration string."""
    dig = draft.get("digitization") or {}
    comps = list(draft.get("components") or [])
    if len(comps) != 2:
        return None
    structured = dig.get("axes")
    if isinstance(structured, dict):
        try:
            return _from_axes_dict(structured, comps)
        except (KeyError, TypeError, ValueError):
            pass
    cal = dig.get("calibration")
    if isinstance(cal, str) and cal.strip():
        return _from_calibration_text(cal, comps)
    return None


def liquidus_x_wt(point: Sequence[float], *, x_component: str, components: Sequence[str]) -> float:
    """First coordinate of a liquidus point is wt% of the x-axis component."""
    if len(point) < 2:
        raise ValueError("liquidus point needs [wt%, °C]")
    return float(point[0])


def _from_axes_dict(data: dict[str, Any], components: Sequence[str]) -> BinaryAxes:
    if "xComponent" in data:
        x_comp = str(data["xComponent"])
    elif len(components) == 2:
        # Atlas binaries usually put the composition axis on the second component
        x_comp = str(components[1])
    else:
        x_comp = str(components[0])
    other = str(data.get("otherComponent") or next(c for c in components if c != x_comp))
    x = data["x"]
    y = data["y"]
    ref = data.get("refPixel") or [0.0, 0.0]
    return BinaryAxes(
        x_component=x_comp,
        other_component=other,
        x=AxisMap(tuple(float(v) for v in x["values"]), tuple(float(v) for v in x["pixels"])),
        y=AxisMap(tuple(float(v) for v in y["values"]), tuple(float(v) for v in y["pixels"])),
        bottom_slope=float(data.get("bottomSlope") or 0.0),
        left_slope=float(data.get("leftSlope") or 0.0),
        ref_px=float(ref[0]),
        ref_py=float(ref[1]),
    )


_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s*→\s*(-?\d+(?:\.\d+)?)")
_LEFT_SLOPE = re.compile(r"dx/dy\s*=\s*([+-]?\d+(?:\.\d+)?)", re.I)
_BOTTOM_ROT = re.compile(r"frame bottom\s*([+-]?\d+(?:\.\d+)?)\s*px over\s*(\d+(?:\.\d+)?)\s*px", re.I)
_X_COMP = re.compile(r"mass%\s+(\S+)\s+ticks", re.I)


def _from_calibration_text(text: str, components: Sequence[str]) -> BinaryAxes | None:
    m_x = re.search(r"x:\s*(.+?)\(piecewise linear\)", text, re.I | re.S)
    m_y = re.search(r"y:\s*ticks\s*°C\s*(.+?);", text, re.I | re.S)
    if not m_x or not m_y:
        return None
    x_pairs = _PAIR.findall(m_x.group(1))
    y_pairs = _PAIR.findall(m_y.group(1))
    if len(x_pairs) < 2 or len(y_pairs) < 2:
        return None
    x_values = tuple(float(a) for a, _ in x_pairs)
    x_pixels = tuple(float(b) for _, b in x_pairs)
    y_values = tuple(float(a) for a, _ in y_pairs)
    y_pixels = tuple(float(b) for _, b in y_pairs)
    x_comp_m = _X_COMP.search(text)
    x_comp = x_comp_m.group(1) if x_comp_m else (components[1] if len(components) == 2 else components[0])
    if x_comp not in components and len(components) == 2:
        x_comp = components[1]
    other = next(c for c in components if c != x_comp)
    left = 0.0
    lm = _LEFT_SLOPE.search(text)
    if lm:
        left = float(lm.group(1))
    bottom = 0.0
    bm = _BOTTOM_ROT.search(text)
    if bm:
        rise = float(bm.group(1))
        run = float(bm.group(2)) or 1.0
        bottom = rise / run
    ref_px = float(x_pixels[0])
    ref_py = float(y_pixels[0])
    return BinaryAxes(
        x_component=str(x_comp),
        other_component=str(other),
        x=AxisMap(x_values, x_pixels),
        y=AxisMap(y_values, y_pixels),
        bottom_slope=bottom,
        left_slope=left,
        ref_px=ref_px,
        ref_py=ref_py,
    )


def _interp_extrapolate(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
    if x >= xs[-1]:
        return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
    # Manual interp to avoid numpy dependency in the service
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]

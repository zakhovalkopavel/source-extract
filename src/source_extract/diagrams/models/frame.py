"""
source_extract.diagrams.models.frame — Detected plot frame of a binary diagram.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Frame:
    """Four frame lines, each as offset + slope.

    Horizontal edges: ``y = offset + slope · x``. Vertical edges: ``x = offset + slope · y``.
    """

    top: tuple[float, float]
    bottom: tuple[float, float]
    left: tuple[float, float]
    right: tuple[float, float]
    line_width: float = 4.0

    def top_y(self, x: float) -> float:
        return self.top[0] + self.top[1] * x

    def bottom_y(self, x: float) -> float:
        return self.bottom[0] + self.bottom[1] * x

    def left_x(self, y: float) -> float:
        return self.left[0] + self.left[1] * y

    def right_x(self, y: float) -> float:
        return self.right[0] + self.right[1] * y

    def corners(self) -> dict[str, tuple[float, float]]:
        """Approximate corners (one fixed-point step is enough for small slopes)."""
        out = {}
        for name, h, v in (
            ("topLeft", self.top_y, self.left_x),
            ("topRight", self.top_y, self.right_x),
            ("bottomLeft", self.bottom_y, self.left_x),
            ("bottomRight", self.bottom_y, self.right_x),
        ):
            y = h(v(h(0.0)))
            x = v(y)
            out[name] = (x, h(x))
        return out

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.left_x(y) + margin <= x <= self.right_x(y) - margin
            and self.top_y(x) + margin <= y <= self.bottom_y(x) - margin
        )

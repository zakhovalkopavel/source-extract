"""
source_extract.diagrams.models.ternary_calibration — Pixel → wt% triple for a ternary diagram.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_WARP_STEPS = 20


@dataclass
class TernaryCalibration:
    """Barycentric map from the three corner pixels, with an optional quadratic warp.

    ``corners`` maps each component to its corner pixel in stored coordinates.
    ``warp`` is the 6 × 2 matrix C of ``digitization.warpCorrection`` (features
    ``[1, x, y, x², xy, y²]``, ``x = (px − 1100)/1000``, ``y = (py − 1100)/1000``).
    ``pixel_origin`` is added to stored pixels to obtain page pixels.
    """

    components: list[str]
    corners: dict[str, tuple[float, float]]
    warp: list[list[float]] | None = None
    pixel_origin: tuple[float, float] = field(default=(0.0, 0.0))

    def __post_init__(self) -> None:
        matrix = np.array(
            [
                [self.corners[c][0] for c in self.components],
                [self.corners[c][1] for c in self.components],
                [1.0, 1.0, 1.0],
            ]
        )
        self._inverse = np.linalg.inv(matrix)

    @classmethod
    def from_system(cls, system: dict, pixel_origin: tuple[float, float] = (0.0, 0.0)) -> "TernaryCalibration":
        digitization = system["digitization"]
        corners = {k: (float(v[0]), float(v[1])) for k, v in digitization["calibration"].items()}
        warp = digitization.get("warpCorrection", {}).get("C") if isinstance(digitization.get("warpCorrection"), dict) else None
        return cls(components=list(system["components"]), corners=corners, warp=warp, pixel_origin=pixel_origin)

    def page_to_stored(self, px: float, py: float) -> tuple[float, float]:
        return px - self.pixel_origin[0], py - self.pixel_origin[1]

    def stored_to_page(self, px: float, py: float) -> tuple[float, float]:
        return px + self.pixel_origin[0], py + self.pixel_origin[1]

    def ideal(self, px: float, py: float) -> tuple[float, float]:
        if self.warp is None:
            return px, py
        x = (px - 1100.0) / 1000.0
        y = (py - 1100.0) / 1000.0
        features = np.array([1.0, x, y, x * x, x * y, y * y])
        out = features @ np.array(self.warp)
        return float(out[0]), float(out[1])

    def to_wt(self, page_px: float, page_py: float) -> dict[str, float]:
        """wt% of each component at a page pixel."""
        sx, sy = self.page_to_stored(page_px, page_py)
        ix, iy = self.ideal(sx, sy)
        weights = self._inverse @ np.array([ix, iy, 1.0]) * 100.0
        return {c: float(w) for c, w in zip(self.components, weights)}

    def to_page(self, wt: list[float] | dict[str, float]) -> tuple[float, float]:
        """Page pixel of a wt% triple (inverse of ``to_wt``; the warp is inverted by fixed-point steps)."""
        values = np.array([wt[c] for c in self.components] if isinstance(wt, dict) else wt, dtype=float)
        target = np.linalg.inv(self._inverse) @ (values / values.sum())
        sx, sy = float(target[0]), float(target[1])
        if self.warp is not None:
            for _ in range(_WARP_STEPS):
                ix, iy = self.ideal(sx, sy)
                sx, sy = sx + float(target[0]) - ix, sy + float(target[1]) - iy
        return self.stored_to_page(sx, sy)

"""
source_extract.diagrams.models.traced_curve — Result of tracing one curve on the scan.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TracedCurve:
    """Pixel path (stroke centre, page pixels) and the non-ink length it crossed.

    ``kind`` (ternary curves): ``boundary``, ``isotherm``, ``inversion`` or ``immiscibility``;
    ``temperature_C`` is set for isotherms. ``arrow`` (boundary segments) is the
    stored printed arrow: ``>`` along ``pixels``, ``<`` against, ``<>`` away from
    the middle, ``?`` not readable, None not recorded. ``inferred`` marks an isotherm
    whose temperature is not printed (config ``inferred``).
    """

    pixels: list[tuple[float, float]]
    gap_px: float = 0.0
    label: str = ""
    points: list[tuple[float, float]] = field(default_factory=list)
    kind: str = ""
    temperature_C: float | None = None
    arrow: str | None = None
    inferred: bool = False

    @property
    def start(self) -> tuple[float, float]:
        return self.pixels[0]

    @property
    def end(self) -> tuple[float, float]:
        return self.pixels[-1]

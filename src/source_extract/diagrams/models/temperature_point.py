"""
source_extract.diagrams.models.temperature_point — A point of a ternary with a printed temperature and its field approximations.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TemperaturePoint:
    """``pixel`` is a page pixel; ``approx`` maps each adjacent phase with a fitted surface to its value there (°C).

    ``label`` names the point (invariant id, or ``<phase> inversion``).
    """

    label: str
    pixel: tuple[float, float]
    temperature_C: float
    approx: dict[str, float] = field(default_factory=dict)

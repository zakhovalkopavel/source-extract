"""
source_extract.diagrams.config.trace_segment_spec — One segment of a liquidus branch in a binary config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class TraceSegmentSpec:
    """``trace`` follows the ink, ``straight`` joins two references, ``flat`` keeps the temperature.

    ``from_ref`` / ``to_ref`` default to the branch ends (first / last segment)
    or to the neighbouring segment's reference.
    """

    KINDS: ClassVar[tuple[str, ...]] = ("trace", "straight", "flat")

    kind: str
    from_ref: str | None = None
    to_ref: str | None = None
    seed_pixel: tuple[float, float] | None = None
    waypoints: list[tuple[float, float]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TraceSegmentSpec":
        seed = data.get("seedPixel")
        return cls(
            kind=data["kind"],
            from_ref=data.get("from"),
            to_ref=data.get("to"),
            seed_pixel=(float(seed[0]), float(seed[1])) if seed else None,
            waypoints=[(float(p[0]), float(p[1])) for p in data.get("waypoints", [])],
        )

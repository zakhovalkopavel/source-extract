"""
source_extract.diagrams.config.liquidus_branch_spec — One liquidus branch in a binary config.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.diagrams.config.trace_segment_spec import TraceSegmentSpec


@dataclass
class LiquidusBranchSpec:
    """Liquidus of one phase between two references.

    References: ``end:<phase>`` (end-member melting point), ``<id>`` (invariant
    liquid), ``<id>:second`` (second liquid of a monotectic).
    """

    phase: str
    from_ref: str
    to_ref: str
    segments: list[TraceSegmentSpec]
    grid: list[float] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "LiquidusBranchSpec":
        return cls(
            phase=data["phase"],
            from_ref=data["from"],
            to_ref=data["to"],
            segments=[TraceSegmentSpec.from_dict(s) for s in data["segments"]],
            grid=list(data.get("grid", [])),
        )

    def resolved_segments(self) -> list[TraceSegmentSpec]:
        """Segments with every ``from_ref`` / ``to_ref`` filled in."""
        out: list[TraceSegmentSpec] = []
        current = self.from_ref
        for index, segment in enumerate(self.segments):
            start = segment.from_ref or current
            end = segment.to_ref
            if end is None:
                end = self.to_ref if index == len(self.segments) - 1 else (self.segments[index + 1].from_ref)
            if end is None:
                raise ValueError(f"liquidus {self.phase} {self.from_ref}→{self.to_ref}: segment {index} has no end reference")
            out.append(TraceSegmentSpec(segment.kind, start, end, segment.seed_pixel, segment.waypoints))
            current = end
        return out

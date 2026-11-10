"""
source_extract.diagrams.models.system_comparison — Differences between a candidate system file and the dataset file.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemComparison:
    """``differences`` break the tolerance; ``notes`` are changes within it (e.g. polylines filled)."""

    differences: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def within_tolerance(self) -> bool:
        return not self.differences

    def lines(self) -> list[str]:
        if self.within_tolerance and not self.notes:
            return ["identical within tolerance"]
        return [f"DIFF {d}" for d in self.differences] + self.notes

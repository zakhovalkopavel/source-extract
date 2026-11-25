"""Structured correction proposal — never writes data by itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CorrectionProposal:
    """Diff with evidence for a human or explicit auto-accept rule."""

    field: str
    old_value: Any
    new_value: Any
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "old": self.old_value,
            "new": self.new_value,
            "evidence": list(self.evidence),
        }

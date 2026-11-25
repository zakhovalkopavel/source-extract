"""Dataset format id + version pair."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatVersion:
    """Identifies a dataset file schema."""

    format_id: str
    version: int

    def to_dict(self) -> dict[str, int | str]:
        return {"id": self.format_id, "version": self.version}

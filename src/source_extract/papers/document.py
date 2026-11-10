"""Placeholder for future paper layout / region routing APIs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentRegion:
    """One typed region on a page (prose, table, figure, equation, caption, …)."""

    kind: str
    page: int
    bbox: tuple[float, float, float, float] | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Structured paper output (schema TBD)."""

    source_id: str | None = None
    regions: list[DocumentRegion] = field(default_factory=list)

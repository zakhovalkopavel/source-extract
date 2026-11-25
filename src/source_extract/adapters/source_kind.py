"""Adapter capability kinds served by source-extract."""

from __future__ import annotations

from enum import Enum


class SourceKind(str, Enum):
    """Kinds of extraction an adapter may declare."""

    DIAGRAMS = "diagrams"
    TABLES = "tables"
    PAPERS = "papers"

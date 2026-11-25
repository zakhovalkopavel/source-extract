"""Filesystem roots declared by a source adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdapterRoots:
    """current = latest dataset; work = scratch; history = prior versions."""

    current: Path
    work: Path
    history: Path

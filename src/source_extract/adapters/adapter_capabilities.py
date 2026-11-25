"""Capability flags advertised by a source adapter."""

from __future__ import annotations

from dataclasses import dataclass, field

from source_extract.adapters.source_kind import SourceKind


@dataclass(frozen=True)
class AdapterCapabilities:
    """What the host adapter supports without embedding source names in SE."""

    kinds: tuple[SourceKind, ...]
    commands: tuple[str, ...] = ()
    has_nbs_cross_check: bool = False
    has_compound_catalog: bool = False
    format_ids: tuple[str, ...] = field(default_factory=tuple)

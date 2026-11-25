"""SourceAdapter protocol — tiny, no CV imports (avoids cycles)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from source_extract.adapters.adapter_capabilities import AdapterCapabilities
from source_extract.adapters.adapter_roots import AdapterRoots


@runtime_checkable
class SourceAdapter(Protocol):
    """Host-provided adapter: identity, catalog, roots, and command hooks."""

    @property
    def adapter_id(self) -> str:
        """Stable id, e.g. ``phase-diagrams``."""

    @property
    def display_name(self) -> str:
        """Human-readable name for GUI / OpenAPI."""

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Kinds and command ids this adapter serves."""

    def roots(self) -> AdapterRoots:
        """current / work / history filesystem roots."""

    def list_sources(self) -> list[dict[str, Any]]:
        """Source catalog entries (paths, page offsets) — adapter-owned shape."""

    def list_systems(self, source_id: str | None = None) -> list[dict[str, Any]]:
        """Systems / tables known to the adapter."""

    def resolve_config(self, system_id: str) -> Path | None:
        """Map a system id to its config path, if any."""

    def run_command(
        self,
        command_id: str,
        params: dict[str, Any],
        *,
        log: Any | None = None,
    ) -> int:
        """Execute an adapter command; return process-style exit code."""

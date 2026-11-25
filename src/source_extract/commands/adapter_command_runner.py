"""Run a CommandSpec by delegating to a SourceAdapter.run_command."""

from __future__ import annotations

from typing import Any

from source_extract.adapters.adapter_registry import get_registry


class AdapterCommandRunner:
    """Thin bridge: resolved params → adapter hook."""

    def __init__(self, adapter_id: str, command_id: str) -> None:
        self._adapter_id = adapter_id
        self._command_id = command_id

    def __call__(self, params: dict[str, Any]) -> int:
        adapter = get_registry().get(self._adapter_id)
        return adapter.run_command(self._command_id, params)

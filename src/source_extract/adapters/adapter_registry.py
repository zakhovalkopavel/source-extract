"""Discover and hold SourceAdapter instances."""

from __future__ import annotations

import importlib
import os
from importlib import metadata

from source_extract.adapters.source_adapter import SourceAdapter
from source_extract.constants.env_names import SE_ADAPTER_MODULES

ENTRY_POINT_GROUP = "source_extract.adapters"


class AdapterRegistry:
    """Loads adapters from entry points and ``SE_ADAPTER_MODULES``."""

    def __init__(self) -> None:
        self._by_id: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        self._by_id[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> SourceAdapter:
        try:
            return self._by_id[adapter_id]
        except KeyError as exc:
            known = ", ".join(sorted(self._by_id)) or "(none)"
            raise KeyError(f"Unknown adapter {adapter_id!r}; known: {known}") from exc

    def list(self) -> list[SourceAdapter]:
        return [self._by_id[k] for k in sorted(self._by_id)]

    def load_defaults(self) -> None:
        self._load_entry_points()
        self._load_env_modules()

    def _load_entry_points(self) -> None:
        try:
            eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[arg-type]
        for ep in eps:
            loaded = ep.load()
            adapter = loaded() if callable(loaded) and not isinstance(loaded, SourceAdapter) else loaded
            self.register(adapter)

    def _load_env_modules(self) -> None:
        raw = os.environ.get(SE_ADAPTER_MODULES, "").strip()
        if not raw:
            return
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue
            module_name, _, attr = item.partition(":")
            if not attr:
                attr = "get_adapter"
            module = importlib.import_module(module_name)
            factory = getattr(module, attr)
            adapter = factory() if callable(factory) else factory
            self.register(adapter)


_REGISTRY: AdapterRegistry | None = None


def get_registry() -> AdapterRegistry:
    """Process-wide registry; loads defaults on first use."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AdapterRegistry()
        _REGISTRY.load_defaults()
    return _REGISTRY


def reset_registry() -> None:
    """Clear the process-wide registry (tests)."""
    global _REGISTRY
    _REGISTRY = None

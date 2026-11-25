"""Adapter protocol, registry, and capability types."""

from source_extract.adapters.adapter_capabilities import AdapterCapabilities
from source_extract.adapters.adapter_registry import AdapterRegistry, get_registry, reset_registry
from source_extract.adapters.adapter_roots import AdapterRoots
from source_extract.adapters.source_adapter import SourceAdapter
from source_extract.adapters.source_kind import SourceKind

__all__ = [
    "AdapterCapabilities",
    "AdapterRegistry",
    "AdapterRoots",
    "SourceAdapter",
    "SourceKind",
    "get_registry",
    "reset_registry",
]

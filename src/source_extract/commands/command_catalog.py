"""In-memory catalog of CommandSpec instances."""

from __future__ import annotations

from source_extract.commands.command_spec import CommandSpec


class CommandCatalog:
    """Register and look up commands by id."""

    def __init__(self) -> None:
        self._by_id: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        self._by_id[spec.command_id] = spec

    def get(self, command_id: str) -> CommandSpec:
        try:
            return self._by_id[command_id]
        except KeyError as exc:
            known = ", ".join(sorted(self._by_id)) or "(none)"
            raise KeyError(f"Unknown command {command_id!r}; known: {known}") from exc

    def list(self) -> list[CommandSpec]:
        return [self._by_id[k] for k in sorted(self._by_id)]


_CATALOG: CommandCatalog | None = None


def get_catalog() -> CommandCatalog:
    """Process-wide command catalog; registers builtins on first use."""
    global _CATALOG
    if _CATALOG is None:
        from source_extract.commands.register_builtins import register_builtins

        _CATALOG = CommandCatalog()
        register_builtins(_CATALOG)
    return _CATALOG


def reset_catalog() -> None:
    """Clear the process-wide catalog (tests)."""
    global _CATALOG
    _CATALOG = None

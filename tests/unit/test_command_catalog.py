"""Built-in command catalog smoke tests."""

from __future__ import annotations

from source_extract.commands.command_catalog import get_catalog, reset_catalog


def test_builtin_commands_include_extract() -> None:
    reset_catalog()
    catalog = get_catalog()
    ids = {c.command_id for c in catalog.list()}
    assert "extract" in ids
    assert "ocr-region" in ids
    assert "history-list" in ids
    spec = catalog.get("extract")
    assert any(p.name == "system" for p in spec.params)

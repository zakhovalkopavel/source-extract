"""DatasetStore archive / promote tests."""

from __future__ import annotations

from pathlib import Path

from source_extract.versioning.dataset_store import DatasetStore


def test_promote_archives_previous(tmp_path: Path) -> None:
    current = tmp_path / "current"
    history = tmp_path / "history"
    current.mkdir()
    (current / "systems").mkdir()
    first = current / "systems" / "demo.json"
    first.write_text('{"v": 1}', encoding="utf-8")

    store = DatasetStore(current, history)
    src = tmp_path / "candidate.json"
    src.write_text('{"v": 2}', encoding="utf-8")
    manifest = store.promote_file(
        relative_path="systems/demo.json",
        source_path=src,
        dataset_id="demo",
        command="promote",
        adapter_id="phase-diagrams",
    )
    assert first.read_text(encoding="utf-8") == '{"v": 2}'
    assert manifest.previous_version is not None
    archived = history / "demo" / manifest.previous_version / "demo.json"
    assert archived.is_file()
    assert archived.read_text(encoding="utf-8") == '{"v": 1}'
    assert (history / "manifests" / f"{manifest.manifest_id}.json").is_file()

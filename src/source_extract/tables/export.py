"""Export handbook tables to JSON files and an index."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from source_extract.tables.naming import dataset_file_name, debug_file_name


def write_json(path: Path | str, document: dict[str, Any]) -> Path:
    """Write ``document`` as pretty JSON; returns ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def resolve_dataset_path(
    directory: Path | str,
    title: str | None,
    table_id: str,
    tag: str | None = None,
    *,
    no_replace: bool = False,
) -> Path | None:
    """Pick the public dataset path for a table.

    Default: ``<Slug>_(table_<id>).json`` (may overwrite).
    With ``no_replace``: if primary exists, write ``…_(table_<id>).<tag>.json``;
    return ``None`` if that also exists.
    """
    directory = Path(directory)
    primary = directory / dataset_file_name(title, table_id)
    if not no_replace:
        return primary
    if not primary.is_file():
        return primary
    if not tag:
        return None
    stem = primary.name[: -len(".json")]
    alt = directory / f"{stem}.{tag}.json"
    if alt.is_file():
        return None
    return alt


def write_dataset_table(
    directory: Path | str,
    table: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    """Write the public dataset JSON; returns the path written."""
    directory = Path(directory)
    target = Path(path) if path is not None else (
        directory / dataset_file_name(table.get("title"), str(table["id"]))
    )
    return write_json(target, table)


def write_debug_table(
    directory: Path | str,
    table: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    """Write the debug JSON (OCR provenance); returns the path written."""
    directory = Path(directory)
    target = Path(path) if path is not None else (
        directory / debug_file_name(table.get("title"), str(table["id"]))
    )
    return write_json(target, table)


def write_index(
    directory: Path | str,
    tables: list[dict[str, Any]],
    source_path: str,
    *,
    ref_key: str,
    source_name: str | None = None,
    source_year: int | str | None = None,
    merge_existing: bool = False,
) -> Path:
    """Write ``index.json`` listing every parsed table file.

    Source identity (``ref_key``, optional name/year) is passed in — not hard-coded
    to a particular handbook.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "id": t["id"],
            "title": t.get("title"),
            "file": t.get("_file") or dataset_file_name(t.get("title"), str(t["id"])),
            "pages": t.get("pages"),
            "rowCount": len(t.get("rows") or []),
        }
        for t in tables
    ]
    if merge_existing:
        index_path = directory / "index.json"
        if index_path.is_file():
            try:
                prior = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prior = {}
            written = {e["file"] for e in entries}
            for old in prior.get("tables") or []:
                name = old.get("file")
                if name and name not in written:
                    entries.append(old)
            entries.sort(key=lambda e: (str(e.get("id") or ""), str(e.get("file") or "")))
    source: dict[str, Any] = {
        "refKey": ref_key,
        "path": source_path,
    }
    if source_name is not None:
        source["name"] = source_name
    if source_year is not None:
        source["year"] = source_year
    index = {"source": source, "tables": entries}
    return write_json(directory / "index.json", index)


def load_table(path: Path | str) -> dict[str, Any]:
    """Read one table JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))

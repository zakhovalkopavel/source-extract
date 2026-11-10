"""High-level entry: take a source file / parsed payload and save results."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Kind = Literal["table", "diagram", "paper", "auto"]


@dataclass
class ExtractRequest:
    """What to extract and where to write it.

    Callers fill source-specific fields (ref_key, page_offset, title). The
    library shapes/validates/writes the result.
    """

    kind: Kind
    source_path: str | Path
    out_dir: str | Path
    ref_key: str
    # For table handbooks: already-parsed page aggregate (id, header, rows, …).
    parsed_table: dict[str, Any] | None = None
    page_offset: int = 0
    source_name: str | None = None
    source_year: int | str | None = None
    debug_dir: str | Path | None = None
    verify: bool = True


@dataclass
class ExtractResult:
    """Paths and optional verify report after extract_and_save."""

    kind: str
    dataset_path: Path | None = None
    debug_path: Path | None = None
    index_path: Path | None = None
    verify_ok: bool | None = None
    verify_issues: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def extract_and_save(request: ExtractRequest) -> ExtractResult:
    """Dispatch by ``kind``, shape the document, optionally verify, write JSON.

    ``kind="table"`` is implemented (uses ``source_extract.tables``).
    ``diagram`` / ``paper`` / ``auto`` are reserved — raise until wired.
    """
    kind = request.kind
    if kind == "auto":
        kind = _infer_kind(request)

    if kind == "table":
        return _extract_table(request)
    if kind == "diagram":
        raise NotImplementedError(
            "diagram extract_and_save not wired yet; use source_extract.diagrams "
            "APIs directly, or extend pipeline.py"
        )
    if kind == "paper":
        raise NotImplementedError(
            "paper extract_and_save not wired yet; use source_extract.papers "
            "and extend pipeline.py"
        )
    raise ValueError(f"unknown extract kind {request.kind!r}")


def _infer_kind(request: ExtractRequest) -> Kind:
    if request.parsed_table is not None:
        return "table"
    suffix = Path(request.source_path).suffix.lower()
    if suffix in {
        ".pdf",
        ".djvu",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".webp",
        ".bmp",
        ".gif",
    } and request.parsed_table is None:
        # Ambiguous without more signals — prefer paper for mixed docs.
        return "paper"
    return "table"


def _extract_table(request: ExtractRequest) -> ExtractResult:
    from source_extract.tables.dataset import to_dataset_table, to_debug_table
    from source_extract.tables.export import (
        write_dataset_table,
        write_debug_table,
        write_index,
    )
    from source_extract.tables.verify import verify_table

    if not request.parsed_table:
        raise ValueError("ExtractRequest.parsed_table is required for kind='table'")

    dataset = to_dataset_table(
        request.parsed_table,
        default_ref_key=request.ref_key,
        page_offset=request.page_offset,
    )
    out_dir = Path(request.out_dir)
    dataset_path = write_dataset_table(out_dir, dataset)

    debug_path = None
    if request.debug_dir is not None:
        debug = to_debug_table(request.parsed_table, default_ref_key=request.ref_key)
        debug_path = write_debug_table(request.debug_dir, debug)

    index_path = write_index(
        out_dir,
        [{**dataset, "_file": dataset_path.name}],
        str(request.source_path),
        ref_key=request.ref_key,
        source_name=request.source_name,
        source_year=request.source_year,
        merge_existing=True,
    )

    verify_ok = None
    issues: list[dict[str, Any]] = []
    if request.verify:
        report = verify_table(dataset)
        verify_ok = report.ok
        issues = [
            {
                "level": i.level,
                "code": i.code,
                "message": i.message,
                "table_id": i.table_id,
                "row_id": i.row_id,
            }
            for i in report.issues
        ]

    return ExtractResult(
        kind="table",
        dataset_path=dataset_path,
        debug_path=debug_path,
        index_path=index_path,
        verify_ok=verify_ok,
        verify_issues=issues,
    )

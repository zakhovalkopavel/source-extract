"""Shape parsed table dicts into public dataset JSON vs debug JSON."""
from __future__ import annotations

from typing import Any

from source_extract.tables.columns import (
    attach_column_units,
    column_keys,
    columns_from_header,
    expand_row,
)


def shape_columns(parsed: dict[str, Any]) -> list[dict[str, str | None]]:
    """Build ``[{key, header, unit}, …]`` from ``header`` / ``columns`` on ``parsed``."""
    header_line = parsed.get("header")
    existing = parsed.get("columns")
    if (
        isinstance(existing, list)
        and existing
        and isinstance(existing[0], dict)
        and "key" in existing[0]
    ):
        return [dict(c) for c in existing]
    if isinstance(header_line, dict):
        keys = (
            list(existing)
            if isinstance(existing, list) and existing and isinstance(existing[0], str)
            else list(header_line.keys())
        )
        return [
            {"key": str(k), "header": str(header_line.get(k, k)), "unit": None}
            for k in keys
        ]
    columns = columns_from_header(header_line if isinstance(header_line, str) else None)
    if len(columns) == 3 and parsed.get("rows"):
        n_vals = len((parsed["rows"][0] or {}).get("values") or [])
        for i in range(1, n_vals + 1):
            key = f"value_{i}"
            columns.append({"key": key, "header": key, "unit": None})
    return columns


def pages_from_parsed(
    parsed: dict[str, Any],
    *,
    page_offset: int = 0,
) -> dict[str, Any]:
    """Resolve ``pages`` from ``pages``, ``printedPages``, or ``sourcePages`` − offset.

    Adapters map format-specific page spans (e.g. DjVu page indexes) into
    ``sourcePages`` before calling.
    """
    pages = parsed.get("pages")
    if pages is not None:
        return pages
    printed = parsed.get("printedPages") or {}
    source = parsed.get("sourcePages") or {}
    if printed:
        return {"first": printed.get("first"), "last": printed.get("last")}
    if source:
        return {
            "first": (source.get("first") or 0) - page_offset,
            "last": (source.get("last") or 0) - page_offset,
        }
    return {"first": None, "last": None}


def to_dataset_table(
    parsed: dict[str, Any],
    *,
    default_ref_key: str | None = None,
    page_offset: int = 0,
) -> dict[str, Any]:
    """Public processed-table document (no OCR provenance)."""
    columns = attach_column_units(shape_columns(parsed), parsed.get("equation"))
    pages = pages_from_parsed(parsed, page_offset=page_offset)
    rows = [expand_row(r, columns, keep_debug=False) for r in parsed.get("rows") or []]
    ref = parsed.get("refKey") or default_ref_key
    return {
        "id": parsed["id"],
        "title": parsed.get("title"),
        "refKey": ref,
        "equation": parsed.get("equation"),
        "columns": columns,
        "pages": pages,
        "rows": rows,
    }


def to_debug_table(
    parsed: dict[str, Any],
    *,
    default_ref_key: str | None = None,
) -> dict[str, Any]:
    """Debug document: dataset fields + OCR provenance + unparsed."""
    header_line = parsed.get("header")
    columns = attach_column_units(shape_columns(parsed), parsed.get("equation"))
    pages = parsed.get("pages")
    if pages is None:
        printed = parsed.get("printedPages") or {}
        pages = {
            "first": printed.get("first"),
            "last": printed.get("last"),
        }
    # Rows match the public dataset shape (no per-row ``raw`` / page fields).
    # OCR provenance stays on the document: engine/headerRaw/sourcePages/unparsed.
    rows = [expand_row(r, columns, keep_debug=False) for r in parsed.get("rows") or []]
    ref = parsed.get("refKey") or default_ref_key
    return {
        "id": parsed["id"],
        "title": parsed.get("title"),
        "refKey": ref,
        "engine": parsed.get("engine"),
        "backend": parsed.get("backend"),
        "model": parsed.get("model"),
        "quant": parsed.get("quant"),
        "dpi": parsed.get("dpi"),
        "equation": parsed.get("equation"),
        "headerRaw": header_line if isinstance(header_line, str) else None,
        "columns": columns,
        "pages": pages,
        "sourcePages": parsed.get("sourcePages"),
        "rows": rows,
        "unparsed": list(parsed.get("unparsed") or []),
    }


# Re-export for callers that only import dataset.
__all__ = [
    "column_keys",
    "pages_from_parsed",
    "shape_columns",
    "to_dataset_table",
    "to_debug_table",
]

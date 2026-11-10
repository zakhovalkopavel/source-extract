"""Verify handbook table JSON shape and internal consistency."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_extract.tables.columns import column_keys


@dataclass
class VerifyIssue:
    """One problem found while checking a table or index."""

    level: str  # error | warning
    code: str
    message: str
    table_id: str | None = None
    row_id: Any = None


@dataclass
class VerifyReport:
    """Result of verifying one or more tables."""

    issues: list[VerifyIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def add(
        self,
        level: str,
        code: str,
        message: str,
        *,
        table_id: str | None = None,
        row_id: Any = None,
    ) -> None:
        self.issues.append(
            VerifyIssue(
                level=level,
                code=code,
                message=message,
                table_id=table_id,
                row_id=row_id,
            )
        )


_IDENTITY = frozenset({"id", "formula", "name"})
_DEBUG_ROW_KEYS = frozenset({"sourcePage", "raw", "formulaRaw", "unparsedTail"})


def verify_table(
    table: dict[str, Any],
    *,
    require_units: bool = False,
    allow_debug_row_keys: bool = False,
) -> VerifyReport:
    """Check one dataset (or debug) table document."""
    report = VerifyReport()
    tid = str(table.get("id") or "") or None

    if not table.get("id"):
        report.add("error", "missing_id", "table.id is required", table_id=tid)
    if "columns" not in table:
        report.add("error", "missing_columns", "table.columns is required", table_id=tid)
        return report
    if "rows" not in table:
        report.add("error", "missing_rows", "table.rows is required", table_id=tid)
        return report

    columns = table["columns"]
    if not isinstance(columns, list) or not columns:
        report.add("error", "bad_columns", "columns must be a non-empty list", table_id=tid)
        return report

    keys: list[str] = []
    if isinstance(columns[0], dict):
        seen: set[str] = set()
        for i, col in enumerate(columns):
            if not isinstance(col, dict) or "key" not in col:
                report.add(
                    "error",
                    "bad_column_entry",
                    f"columns[{i}] must be an object with key/header/unit",
                    table_id=tid,
                )
                continue
            key = str(col["key"])
            if key in seen:
                report.add(
                    "error",
                    "duplicate_column_key",
                    f"duplicate column key {key!r}",
                    table_id=tid,
                )
            seen.add(key)
            keys.append(key)
            if "header" not in col:
                report.add(
                    "warning",
                    "missing_header",
                    f"column {key!r} has no header",
                    table_id=tid,
                )
            if "unit" not in col:
                report.add(
                    "warning",
                    "missing_unit_field",
                    f"column {key!r} has no unit field",
                    table_id=tid,
                )
            elif require_units and col.get("unit") is None and key not in _IDENTITY:
                # Coefficients often legitimately null; only warn when require_units.
                if key not in {"A", "B", "C", "D", "E", "n", "ZC", "OMEGA", "State"}:
                    report.add(
                        "warning",
                        "null_unit",
                        f"column {key!r} unit is null",
                        table_id=tid,
                    )
            if key.startswith("value_extra"):
                report.add(
                    "error",
                    "value_extra_column",
                    f"column {key!r} should not appear (align values into named columns)",
                    table_id=tid,
                )
    else:
        # Legacy string-list columns
        keys = [str(k) for k in columns]
        report.add(
            "warning",
            "legacy_columns",
            "columns is a string list; prefer [{key, header, unit}, …]",
            table_id=tid,
        )

    key_set = set(keys)
    for ident in ("id", "formula", "name"):
        if ident not in key_set:
            report.add(
                "warning",
                "missing_identity_column",
                f"columns missing identity key {ident!r}",
                table_id=tid,
            )

    rows = table.get("rows") or []
    if not isinstance(rows, list):
        report.add("error", "bad_rows", "rows must be a list", table_id=tid)
        return report

    allowed_row = key_set | (_DEBUG_ROW_KEYS if allow_debug_row_keys else set())
    seen_ids: set[Any] = set()
    for row in rows:
        if not isinstance(row, dict):
            report.add("error", "bad_row", "row is not an object", table_id=tid)
            continue
        rid = row.get("id")
        if rid is None:
            report.add("error", "row_missing_id", "row has no id", table_id=tid)
        elif rid in seen_ids:
            report.add(
                "error",
                "duplicate_row_id",
                f"duplicate row id {rid!r}",
                table_id=tid,
                row_id=rid,
            )
        else:
            seen_ids.add(rid)

        for field in ("formula", "name"):
            if field not in row:
                report.add(
                    "warning",
                    "row_missing_field",
                    f"row missing {field!r}",
                    table_id=tid,
                    row_id=rid,
                )

        for k in row:
            if k not in allowed_row and not (
                allow_debug_row_keys and k in _DEBUG_ROW_KEYS
            ):
                if k.startswith("value_extra"):
                    report.add(
                        "error",
                        "row_value_extra",
                        f"row has {k!r}; should be mapped into a named column",
                        table_id=tid,
                        row_id=rid,
                    )
                else:
                    report.add(
                        "warning",
                        "row_unknown_key",
                        f"row has key {k!r} not listed in columns",
                        table_id=tid,
                        row_id=rid,
                    )

        for k in keys:
            if k in _IDENTITY:
                continue
            if k not in row:
                report.add(
                    "warning",
                    "row_missing_column",
                    f"row missing column {k!r}",
                    table_id=tid,
                    row_id=rid,
                )

    return report


def verify_index(
    index: dict[str, Any],
    *,
    tables_by_id: dict[str, dict[str, Any]] | None = None,
) -> VerifyReport:
    """Check ``index.json`` shape; optionally cross-check against loaded tables."""
    report = VerifyReport()
    source = index.get("source")
    if not isinstance(source, dict):
        report.add("error", "index_missing_source", "index.source must be an object")
    else:
        if not source.get("refKey"):
            report.add("error", "index_missing_refKey", "index.source.refKey is required")
        if "path" not in source:
            report.add("warning", "index_missing_path", "index.source.path is missing")

    tables = index.get("tables")
    if not isinstance(tables, list):
        report.add("error", "index_bad_tables", "index.tables must be a list")
        return report

    seen_files: set[str] = set()
    for entry in tables:
        if not isinstance(entry, dict):
            report.add("error", "index_bad_entry", "index entry is not an object")
            continue
        eid = entry.get("id")
        efile = entry.get("file")
        if not eid:
            report.add("error", "index_entry_missing_id", "index entry missing id")
        if not efile:
            report.add(
                "error",
                "index_entry_missing_file",
                f"index entry {eid!r} missing file",
                table_id=str(eid) if eid else None,
            )
        elif efile in seen_files:
            report.add(
                "error",
                "index_duplicate_file",
                f"duplicate index file {efile!r}",
                table_id=str(eid) if eid else None,
            )
        else:
            seen_files.add(str(efile))

        if tables_by_id is not None and eid is not None:
            table = tables_by_id.get(str(eid))
            if table is None:
                report.add(
                    "error",
                    "index_table_missing",
                    f"index lists table {eid!r} but it was not loaded",
                    table_id=str(eid),
                )
            else:
                expected = len(table.get("rows") or [])
                listed = entry.get("rowCount")
                if listed is not None and listed != expected:
                    report.add(
                        "error",
                        "index_rowCount_mismatch",
                        f"index rowCount={listed} but table has {expected} rows",
                        table_id=str(eid),
                    )

    if tables_by_id is not None:
        for tid, table in tables_by_id.items():
            sub = verify_table(table)
            for issue in sub.issues:
                if issue.table_id is None:
                    issue.table_id = tid
                report.issues.append(issue)

    return report

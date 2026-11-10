"""source_extract.tables — tabular-handbook helpers.

Modules:
  columns  — header coalesce, units, align_values, expand_row
  naming   — dataset file slugs
  dataset  — to_dataset_table / to_debug_table
  export   — write JSON, index, load_table
  verify   — schema / consistency checks
  progress — heartbeat helper
"""
from source_extract.tables.columns import (
    align_values,
    attach_column_units,
    coalesce_header_labels,
    column_keys,
    columns_from_header,
    expand_row,
    header_tokens,
    parse_equation_units,
)
from source_extract.tables.dataset import to_dataset_table, to_debug_table
from source_extract.tables.export import (
    load_table,
    resolve_dataset_path,
    write_dataset_table,
    write_debug_table,
    write_index,
    write_json,
)
from source_extract.tables.naming import dataset_file_name, debug_file_name, title_slug
from source_extract.tables.verify import VerifyIssue, VerifyReport, verify_index, verify_table

__all__ = [
    "align_values",
    "attach_column_units",
    "coalesce_header_labels",
    "column_keys",
    "columns_from_header",
    "dataset_file_name",
    "debug_file_name",
    "expand_row",
    "header_tokens",
    "load_table",
    "parse_equation_units",
    "resolve_dataset_path",
    "title_slug",
    "to_dataset_table",
    "to_debug_table",
    "VerifyIssue",
    "VerifyReport",
    "verify_index",
    "verify_table",
    "write_dataset_table",
    "write_debug_table",
    "write_index",
    "write_json",
]

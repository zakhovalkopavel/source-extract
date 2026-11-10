# source-extract

**One library:** take a **source** (tabular handbooks, diagram figures, or mixed papers) and **save structured results**.

| Subpackage | Role |
| --- | --- |
| `source_extract.tables` | Tabular extract: columns/units, dataset shape, export, verify |
| `source_extract.diagrams` | Figure/diagram CV (detect, trace, calibrate, overlay) |
| `source_extract.papers` | Mixed scientific papers (scaffold) |
| `source_extract.pipeline` | High-level `extract_and_save(ExtractRequest)` |

Depends on **`page-ocr`** for recognition (local or Modal). Provision OCR first (`vendor/page-ocr/install.sh --all` or `python -m page_ocr install --all`), then `pip install -e .` here. Sources may be **PDF**, **DjVu**, or a **raster image** (PNG/JPEG/…); examples below use PDF.

Host apps keep **source-specific** catalogs, refs, column schemas, and cross-checks; this package is generic extract (shape / CV / export / verify).

## Example (tables)

```python
from source_extract import ExtractRequest, extract_and_save

result = extract_and_save(
    ExtractRequest(
        kind="table",
        source_path="…/handbook.pdf",
        out_dir="…/processed/handbook",
        ref_key="HandbookRef",
        parsed_table=parsed,  # from the host’s page parser
        page_offset=0,
        debug_dir="…/debug",
    )
)
assert result.verify_ok
```

## Layout

```text
src/source_extract/
  pipeline.py
  tables/
  diagrams/
  papers/
```

This directory is its **own git repository** (submodule path `vendor/source-extract`).

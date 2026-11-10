"""source_extract — source file in → structured result out.

One library for:
  - tabular handbooks (``tables``)
  - figure/diagram CV (``diagrams``)
  - mixed scientific papers (``papers``)

OCR is a separate dependency (``page-ocr``). Host apps keep thin source
wrappers (paths, catalogs, quirks); this package owns extract + export.
"""
from source_extract.pipeline import ExtractRequest, ExtractResult, extract_and_save

__all__ = [
    "ExtractRequest",
    "ExtractResult",
    "extract_and_save",
]

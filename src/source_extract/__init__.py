"""source_extract — source file in → structured result out.

One library + single entry point (CLI / API / GUI) for:
  - tabular handbooks (``tables``)
  - figure/diagram CV (``diagrams``)
  - mixed scientific papers (``papers``)

OCR is a separate dependency (``page-ocr``). Host apps keep thin source
adapters (paths, catalogs, quirks); this package owns extract + export +
command/job/review orchestration.
"""
from source_extract.pipeline import ExtractRequest, ExtractResult, extract_and_save

__version__ = "0.1.0"

__all__ = [
    "ExtractRequest",
    "ExtractResult",
    "__version__",
    "extract_and_save",
]

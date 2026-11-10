"""
source_extract.diagrams.config.source_registry — Reads sources.json: PDF paths, page mappings, figures, status keys.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class SourceRegistry:
    """Access to ``<dataset>/sources.json``.

    PDF paths in sources.json are relative to ``root``. When ``root`` is omitted,
    it defaults to three parents above the dataset folder (common host layout);
    adapters should pass an explicit ``root`` when their layout differs.
    """

    def __init__(self, dataset_dir: Path | str, *, root: Path | str | None = None):
        self.dataset_dir = Path(dataset_dir)
        self.data = json.loads((self.dataset_dir / "sources.json").read_text(encoding="utf-8"))
        self.root = Path(root).resolve() if root is not None else self.dataset_dir.resolve().parents[2]

    @property
    def status_keys(self) -> list[str]:
        return list(self.data["statusLegend"].keys())

    def source(self, ref: str) -> dict:
        try:
            return self.data["sources"][ref]
        except KeyError as exc:
            raise KeyError(f"unknown source '{ref}' in sources.json") from exc

    def pdf_path(self, ref: str) -> Path:
        file = self.source(ref).get("file")
        if not file:
            raise FileNotFoundError(f"source '{ref}' has no file")
        return self.root / file

    def page_offset(self, ref: str) -> int:
        """``pdfPage − printedPage`` from the ``pageMapping`` text (``pdfPage = printedPage + N``)."""
        mapping = self.source(ref).get("pageMapping", "")
        match = re.search(r"pdfPage\s*=\s*printedPage\s*([+-])\s*(\d+)", mapping)
        if not match:
            raise ValueError(f"source '{ref}' has no parsable pageMapping")
        value = int(match.group(2))
        return value if match.group(1) == "+" else -value

    def figures(self, ref: str) -> list[dict]:
        return list(self.source(ref).get("figures", []))

    def figure(self, ref: str, figure: str) -> dict | None:
        return next((f for f in self.figures(ref) if f["figure"] == figure), None)

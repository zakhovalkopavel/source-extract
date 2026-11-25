"""LLM tool functions the assistant can call (bounded, recorded)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from source_extract.assist.correction_proposal import CorrectionProposal
from source_extract.models.ocr.ocr_region_runner import OcrRegionRunner


class AssistTools:
    """Tool surface: OCR, lookup, compare, propose, transform."""

    def __init__(self, ocr: OcrRegionRunner | None = None) -> None:
        self._ocr = ocr or OcrRegionRunner()

    def ocr_region(
        self,
        image: Any,
        box: tuple[int, int, int, int],
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self._ocr.ocr_region(image, box, **kwargs)]

    def lookup_context(self, path: str | Path) -> dict[str, Any]:
        """Read already-extracted JSON for confirmation."""
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "error": f"missing: {p}"}
        import json

        return {"ok": True, "path": str(p), "data": json.loads(p.read_text(encoding="utf-8"))}

    def compare_sources(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        keys = set(left) | set(right)
        return {
            "onlyLeft": sorted(k for k in keys if k in left and k not in right),
            "onlyRight": sorted(k for k in keys if k in right and k not in left),
            "changed": sorted(k for k in keys if k in left and k in right and left[k] != right[k]),
        }

    def propose_correction(
        self,
        field: str,
        old_value: Any,
        new_value: Any,
        evidence: list[str] | None = None,
    ) -> dict[str, Any]:
        return CorrectionProposal(field, old_value, new_value, evidence or []).to_dict()

    def transform_data(
        self,
        data: dict[str, Any],
        *,
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        """Stub reshape when a change note defines the mapping."""
        if from_version == to_version:
            return data
        return {
            **data,
            "format": {"migratedFrom": from_version, "version": to_version},
        }

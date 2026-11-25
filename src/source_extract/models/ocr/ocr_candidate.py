"""OCR result candidate — never treated as ground truth alone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OcrCandidate:
    """One engine's reading of a region."""

    text: str
    confidence: float
    engine: str
    box: tuple[int, int, int, int]
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "engine": self.engine,
            "box": list(self.box),
            "parameters": self.parameters,
        }

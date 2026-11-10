"""
source_extract.diagrams.models.review_item — One item of the review list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ReviewItem:
    KINDS: ClassVar[tuple[str, ...]] = (
        "label-drawing",
        "unlabelled",
        "cross-check-conflict",
        "cross-check-approximate",
        "trace-gap",
        "tick-residual",
        "ocr-differs",
        "dropped-points",
        "track-point-off-curve",
        "isotherm-temperature",
        "isotherm-conflict",
    )

    kind: str
    subject: str
    message: str

    def __post_init__(self) -> None:
        if self.kind not in self.KINDS:
            raise ValueError(f"unknown review kind '{self.kind}'")

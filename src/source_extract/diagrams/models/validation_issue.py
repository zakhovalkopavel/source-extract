"""
source_extract.diagrams.models.validation_issue — One finding of the dataset validator.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationIssue:
    code: str
    level: str
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.code} {self.file}: {self.message}"

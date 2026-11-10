"""
source_extract.diagrams.constants.comparison_tolerance — Curve tolerance between a candidate and the dataset file.

A curve point agrees when the other curve passes through the box ± composition × ± temperature around it.
"""
from __future__ import annotations

COMPARISON_TOLERANCE: dict[str, float] = {
    "temperature_C": 3.0,
    "composition_wt": 0.2,
}

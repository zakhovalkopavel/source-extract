"""Resolve invariant tags (A3S2, mullite, …) to compound melting points."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP


def _compounds_path() -> Path:
    return RP.dataset_dir() / "compounds.json"


def load_compounds() -> list[dict[str, Any]]:
    path = _compounds_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("compounds") or [])


def resolve_compound(tag: str, compounds: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Match ``tag`` to a compounds.json entry by id or cement ``notation`` (A3S2)."""
    key = str(tag or "").strip()
    if not key:
        return None
    rows = compounds if compounds is not None else load_compounds()
    lower = key.lower()
    for c in rows:
        if str(c.get("id") or "").lower() == lower:
            return c
    for c in rows:
        notation = str(c.get("notation") or "").strip()
        if notation and notation.lower() == lower:
            return c
    # Notation without separators: cas2 → CAS2
    compact = key.replace("-", "").replace(" ", "").upper()
    for c in rows:
        notation = str(c.get("notation") or "").strip().upper()
        if notation and notation == compact:
            return c
    return None


def melting_from_compound(compound: dict[str, Any]) -> float | None:
    melting = compound.get("melting") or {}
    t = melting.get("temperature_C")
    if t is None or t == "":
        return None
    try:
        return float(t)
    except (TypeError, ValueError):
        return None


def enrich_invariant_from_tag(tag: str) -> dict[str, Any]:
    """Return optional ``temperature_C`` / ``phases`` / ``compoundId`` / ``notation`` for ``tag``."""
    compound = resolve_compound(tag)
    if compound is None:
        return {}
    out: dict[str, Any] = {
        "compoundId": compound.get("id"),
        "notation": compound.get("notation"),
        "phases": [str(compound["id"])] if compound.get("id") else [],
    }
    t = melting_from_compound(compound)
    if t is not None:
        out["temperature_C"] = t
    return out

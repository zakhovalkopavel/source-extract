"""Resolve draft JSON paths across adapter-supplied roots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.binary_axes import is_binary_draft

_DRAFT_SOURCE_ORDER = ("auto-full", "candidates", "systems", "starts", "review-starts")


def _draft_search_roots() -> list[tuple[str, Path]]:
    return RP.draft_search_roots()


def _draft_content_score(data: dict[str, Any]) -> int:
    """How much editable geometry a draft carries (empty auto-full scores 0)."""
    boundaries = data.get("boundaryCurves") or []
    isotherms = data.get("isotherms") or []
    invariants = data.get("invariantPoints") or []
    liquidus = data.get("liquidus") or []
    n_bc = sum(1 for bc in boundaries if bc.get("polyline_wt"))
    n_iso = sum(1 for iso in isotherms if iso.get("polyline_wt"))
    n_liq = sum(1 for br in liquidus if br.get("points"))
    return n_bc * 10 + n_iso * 3 + n_liq * 10 + len(invariants)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _pick_best_draft(found: dict[str, Path]) -> tuple[str, Path]:
    scored: list[tuple[int, int, str, Path]] = []
    for kind, path in found.items():
        data = _load_json(path) or {}
        score = _draft_content_score(data)
        order = _DRAFT_SOURCE_ORDER.index(kind) if kind in _DRAFT_SOURCE_ORDER else 99
        scored.append((score, -order, kind, path))
    scored.sort(reverse=True)
    best_score, _neg_order, best_kind, best_path = scored[0]
    if best_score == 0:
        for kind in _DRAFT_SOURCE_ORDER:
            if kind in found and kind != "auto-full":
                return kind, found[kind]
    return best_kind, best_path


def _resolve_draft_path(system_id: str, preferred: str | None = None) -> tuple[str, Path]:
    """Return (source_kind, json_path) for a system id (case-insensitive stem match).

    A preferred source is honored only when it has geometry; empty auto-full never
    shadows candidates/systems from pd-curves.
    """
    needle = system_id.lower()
    found: dict[str, Path] = {}
    for kind, root in _draft_search_roots():
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            if path.stem.lower() == needle:
                found[kind] = path
                break
    if not found:
        raise FileNotFoundError(f"No draft JSON for {system_id}")
    if preferred and preferred in found:
        data = _load_json(found[preferred]) or {}
        if _draft_content_score(data) > 0:
            return preferred, found[preferred]
        # Preferred is empty — fall through to richest alternate
    return _pick_best_draft(found)


def draft_content_stats(system_id: str, source: str | None = None) -> dict[str, Any]:
    """Counts for a draft (used by analyze jobs / UI).

    When ``source`` is set, read that folder only (even if empty) so callers can
    detect empty auto-full without falling back to candidates.
    """
    needle = system_id.lower()
    if source:
        roots = dict(_draft_search_roots())
        root = roots.get(source)
        path = None
        if root and root.is_dir():
            for p in root.glob("*.json"):
                if p.stem.lower() == needle:
                    path = p
                    break
        if path is None:
            return {
                "draftSource": source,
                "contentScore": 0,
                "n_boundaries": 0,
                "n_isotherms": 0,
                "n_invariants": 0,
            }
        data = _load_json(path) or {}
        kind = source
    else:
        try:
            kind, path = _resolve_draft_path(system_id)
            data = _load_json(path) or {}
        except FileNotFoundError:
            return {
                "draftSource": None,
                "contentScore": 0,
                "n_boundaries": 0,
                "n_isotherms": 0,
                "n_invariants": 0,
            }
    return {
        "draftSource": kind,
        "contentScore": _draft_content_score(data),
        "n_boundaries": len(data.get("boundaryCurves") or []),
        "n_isotherms": len(data.get("isotherms") or []),
        "n_liquidus": len(data.get("liquidus") or []),
        "n_invariants": len(data.get("invariantPoints") or []),
        "diagramKind": "binary" if len(data.get("components") or []) == 2 else "ternary",
    }


def create_system_stub(
    *,
    system_id: str,
    components: list[str],
    system_name: str | None = None,
    figure: str | None = None,
    printed_page: int | None = None,
    pdf_page: int | None = None,
) -> dict[str, Any]:
    """Create an empty ``starts/{id}.json`` stub so a system can be analyzed."""
    sid = str(system_id or "").strip()
    if not sid:
        raise ValueError("systemId is required")
    # Normalise id for filenames
    sid = sid.replace(" ", "-")
    comps = [str(c).strip() for c in (components or []) if str(c).strip()]
    if len(comps) not in (2, 3):
        raise ValueError("Provide 2 components (binary T–x) or 3 (ternary triangle TOP / LEFT / RIGHT)")
    starts = RP.data_dir() / "starts"
    starts.mkdir(parents=True, exist_ok=True)
    # Case-insensitive uniqueness across all draft roots
    needle = sid.lower()
    for _kind, root in _draft_search_roots():
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            if path.stem.lower() == needle:
                raise ValueError(f"System '{path.stem}' already exists ({_kind})")
    name = (system_name or "").strip() or "-".join(comps)
    fig = (figure or "").strip() or None
    if fig and not fig.lower().startswith("fig"):
        fig = f"Fig. {fig}"
    binary = len(comps) == 2
    draft: dict[str, Any] = {
        "system": name,
        "components": comps,
        "units": (
            {"temperature_C": "°C", "liquid_wt": "wt%", "liquidus": f"[wt% {comps[1]}, °C]"}
            if binary
            else {"temperature_C": "°C", "liquid_wt": "wt%"}
        ),
        "source": {
            "ref": "source-extract",
            "figure": fig,
            "diagram": None,
            "printedPage": printed_page,
            "pdfPage": pdf_page,
            "caption": None,
        },
        "digitization": {
            "render": None,
            "calibration": {} if not binary else "",
            "method": "stub created in source-extract review — run Analyze to digitize",
            "check": None,
        },
        "phases": [],
        "invariantPoints": [],
        "inversions": [],
    }
    if binary:
        draft["liquidus"] = []
    else:
        draft["boundaryCurves"] = []
        draft["isotherms"] = []
    path = starts / f"{sid}.json"
    path.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
    return {
        "id": sid,
        "system": name,
        "components": comps,
        "diagramKind": "binary" if binary else "ternary",
        "source": draft["source"],
        "draftSource": "review-starts",
        "availableSources": ["review-starts"],
        "n_invariants": 0,
        "n_boundaries": 0,
        "n_isotherms": 0,
        "n_liquidus": 0,
        "contentScore": 0,
        "has_image": False,
        "has_report": False,
        "path": str(path),
    }


def list_available_systems() -> list[dict[str, Any]]:
    from source_extract.review.session_image import _find_image_path
    RP.ensure_dirs()
    by_id: dict[str, dict[str, Any]] = {}
    for kind, root in _draft_search_roots():
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            data = _load_json(path)
            if data is None:
                continue
            key = path.stem.lower()
            png = _find_image_path(path.stem, path.stem, draft_kind=kind)
            comps = data.get("components", []) or []
            entry = {
                "id": path.stem,
                "system": data.get("system", path.stem),
                "components": comps,
                "diagramKind": "binary" if len(comps) == 2 else "ternary",
                "source": data.get("source"),
                "draftSource": kind,
                "availableSources": [kind],
                "n_invariants": len(data.get("invariantPoints", [])),
                "n_boundaries": len(data.get("boundaryCurves", [])),
                "n_isotherms": len(data.get("isotherms", [])),
                "n_liquidus": len(data.get("liquidus", [])),
                "contentScore": _draft_content_score(data),
                "has_image": png is not None,
                "has_report": (RP.auto_full_dir() / f"{path.stem}.md").is_file(),
            }
            if key not in by_id:
                by_id[key] = entry
                continue
            existing = by_id[key]
            existing["availableSources"] = sorted(
                set(existing.get("availableSources", []) + [kind]),
                key=lambda k: _DRAFT_SOURCE_ORDER.index(k) if k in _DRAFT_SOURCE_ORDER else 99,
            )
            existing["has_image"] = existing["has_image"] or entry["has_image"]
            # Promote to richer draft (empty auto-full loses to candidates)
            better = entry["contentScore"] > existing.get("contentScore", 0) or (
                entry["contentScore"] == existing.get("contentScore", 0)
                and _DRAFT_SOURCE_ORDER.index(kind)
                < _DRAFT_SOURCE_ORDER.index(existing["draftSource"])
            )
            if better:
                for field in (
                    "id",
                    "system",
                    "components",
                    "source",
                    "draftSource",
                    "n_invariants",
                    "n_boundaries",
                    "n_isotherms",
                    "contentScore",
                    "has_image",
                    "has_report",
                ):
                    existing[field] = entry[field]
                existing["has_image"] = entry["has_image"] or existing["has_image"]
    return sorted(by_id.values(), key=lambda e: e["id"].lower())


def load_draft(system_id: str, preferred: str | None = None) -> dict[str, Any]:
    _kind, path = _resolve_draft_path(system_id, preferred=preferred)
    return json.loads(path.read_text(encoding="utf-8"))


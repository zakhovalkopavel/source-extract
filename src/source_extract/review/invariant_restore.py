"""Reload pd-nodes and/or merge invariant points from the on-disk draft."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.draft_resolver import _resolve_draft_path
from source_extract.review.nodes_attach import _attach_nodes
from source_extract.review.session_persist import _push_undo, save_session

# Prefer curated identity sources over empty auto-full when restoring markers.
_INVARIANT_SOURCE_ORDER = ("candidates", "systems", "starts", "review-starts", "auto-full")


def reload_nodes(session: dict[str, Any]) -> dict[str, Any]:
    """Force-refresh ``session.nodes`` from ``nodes/<system>.json`` (keeps draft)."""
    _push_undo(session)
    _attach_nodes(session, force=True)
    session["_lastNodesReload"] = {"count": len(session.get("nodes") or [])}
    save_session(session)
    return session


def _draft_with_most_invariants(
    system_id: str,
    *,
    preferred_source: str | None = None,
) -> tuple[str, Path, list[dict[str, Any]], list[str]]:
    """Pick the on-disk draft richest in ``invariantPoints`` (for identity restore)."""
    needle = system_id.lower()
    found: dict[str, Path] = {}
    for kind, root in RP.draft_search_roots():
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            if path.stem.lower() == needle:
                found[kind] = path
                break
    if preferred_source and preferred_source in found:
        try:
            data = json.loads(found[preferred_source].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        invs = list(data.get("invariantPoints") or [])
        if invs:
            return preferred_source, found[preferred_source], invs, list(data.get("phases") or [])

    best: tuple[int, int, str, Path, list[dict[str, Any]], list[str]] | None = None
    for kind, path in found.items():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        invs = list(data.get("invariantPoints") or [])
        order = (
            _INVARIANT_SOURCE_ORDER.index(kind)
            if kind in _INVARIANT_SOURCE_ORDER
            else 99
        )
        score = (len(invs), -order)
        if best is None or score > (best[0], best[1]):
            best = (len(invs), -order, kind, path, invs, list(data.get("phases") or []))
    if best is not None and best[0] > 0:
        return best[2], best[3], best[4], best[5]

    # Fall back to normal draft resolution (may be empty).
    kind, path = _resolve_draft_path(system_id, preferred=preferred_source)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return kind, path, list(data.get("invariantPoints") or []), list(data.get("phases") or [])


def restore_invariants_from_disk(
    session: dict[str, Any],
    *,
    preferred_source: str | None = None,
) -> dict[str, Any]:
    """Merge missing / incomplete invariants from the disk draft; keep user points.

    - Adds invariantPoints that exist on disk but not in the session
    - Fills blank ``temperature_C`` / empty ``phases`` from disk when session value
      is missing (does not overwrite user-set °C or non-empty phases)
    - Reloads pd-nodes so canvas labels (I#, C#) match the node map again
    - Does **not** replace boundaries / isotherms / calibration
    """
    system_id = session["systemId"]
    preferred = preferred_source or session.get("draftSource")
    draft_kind, _draft_path, disk_invs, disk_phases = _draft_with_most_invariants(
        system_id, preferred_source=preferred
    )
    if not disk_invs and not (session.get("draft") or {}).get("invariantPoints"):
        return session

    _push_undo(session)
    draft = session.setdefault("draft", {})
    current = list(draft.get("invariantPoints") or [])
    by_id = {str(p.get("id")): p for p in current if p.get("id")}
    added = 0
    filled_t = 0
    filled_phases = 0

    for src in disk_invs:
        sid = str(src.get("id") or "")
        if not sid:
            continue
        if sid not in by_id:
            current.append(copy.deepcopy(src))
            by_id[sid] = current[-1]
            added += 1
            continue
        dst = by_id[sid]
        # Never clobber explicit user provenance points' chemistry unless blank
        if dst.get("temperature_C") is None and src.get("temperature_C") is not None:
            dst["temperature_C"] = src.get("temperature_C")
            filled_t += 1
        if not (dst.get("phases") or []) and (src.get("phases") or []):
            dst["phases"] = list(src.get("phases") or [])
            filled_phases += 1
        if dst.get("reaction") in (None, "", "unknown") and src.get("reaction"):
            dst["reaction"] = src.get("reaction")
        if dst.get("type") in (None, "") and src.get("type"):
            dst["type"] = src.get("type")
        # Prefer disk liquid_wt when missing
        if not dst.get("liquid_wt") and src.get("liquid_wt"):
            dst["liquid_wt"] = copy.deepcopy(src["liquid_wt"])
        if not dst.get("notation") and src.get("notation"):
            dst["notation"] = src.get("notation")

    draft["invariantPoints"] = current
    # Keep phase name list complete
    phases = list(draft.get("phases") or [])
    for name in disk_phases:
        if name and name not in phases:
            phases.append(name)
    for inv in current:
        for name in inv.get("phases") or []:
            if name and name not in phases:
                phases.append(name)
    draft["phases"] = phases

    _attach_nodes(session, force=True)
    session["_lastInvariantRestore"] = {
        "draftSource": draft_kind,
        "added": added,
        "filledTemperature": filled_t,
        "filledPhases": filled_phases,
        "total": len(current),
        "nodeCount": len(session.get("nodes") or []),
    }
    save_session(session)
    return session
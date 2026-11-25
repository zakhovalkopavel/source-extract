"""Session file I/O, live overlay persist, undo stack."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.overlay_draw import render_overlay_image
from source_extract.review.session_common import _now
from source_extract.review.session_view import _build_view


def session_path(session_id: str) -> Path:
    return RP.sessions_dir() / f"{session_id}.json"


def save_session(session: dict[str, Any]) -> None:
    RP.ensure_dirs()
    session["updatedAt"] = _now()
    session["view"] = _build_view(session)
    path = session_path(session["id"])
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    _persist_live_overlay(session)


def _persist_live_overlay(session: dict[str, Any]) -> None:
    """Re-render overlay from current draft after every edit.

    Writes ``{system}.review.png`` (does not clobber pd-curves ``{system}.png``).
    """
    try:
        from source_extract.review.overlay_draw import render_confirmed_overlay
    except ImportError:
        return
    system_id = session.get("systemId") or "session"
    session_dest = RP.sessions_dir() / f"{session['id']}.live-overlay.png"
    try:
        render_confirmed_overlay(session, session_dest)
        session.setdefault("image", {})["liveOverlayPath"] = str(session_dest)
    except Exception:
        return
    # Prefer a writable review-overlays/ dir (pipeline overlays/ is often root-owned)
    for root in (
        RP.work_dir() / "review-overlays",
        RP.data_dir() / "overlays",
    ):
        try:
            root.mkdir(parents=True, exist_ok=True)
            work_dest = root / f"{system_id}.png"
            render_confirmed_overlay(session, work_dest)
            break
        except Exception:
            continue


def load_session(session_id: str) -> dict[str, Any]:
    path = session_path(session_id)
    if not path.is_file():
        raise FileNotFoundError(f"Session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions() -> list[dict[str, Any]]:
    from source_extract.review.draft_resolver import _draft_content_score
    from source_extract.review.session_factory import prune_duplicate_sessions

    RP.ensure_dirs()
    prune_duplicate_sessions()
    # One row per system: prefer reviewing with content, else newest
    by_system: dict[str, dict[str, Any]] = {}
    for path in sorted(RP.sessions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = (s.get("systemId") or "").lower()
        if not key:
            continue
        draft = s.get("draft") or {}
        score = _draft_content_score(draft)
        entry = {
            "id": s.get("id"),
            "systemId": s.get("systemId"),
            "system": s.get("system"),
            "draftSource": s.get("draftSource"),
            "status": s.get("status"),
            "updatedAt": s.get("updatedAt"),
            "contentScore": score,
            "n_boundaries": len(draft.get("boundaryCurves") or []),
        }
        prev = by_system.get(key)
        if prev is None:
            by_system[key] = entry
            continue
        # Prefer reviewing over confirmed; then higher content; then already-newest order
        prev_rank = (
            1 if prev.get("status") == "reviewing" else 0,
            int(prev.get("contentScore") or 0),
        )
        new_rank = (
            1 if entry.get("status") == "reviewing" else 0,
            int(entry.get("contentScore") or 0),
        )
        if new_rank > prev_rank:
            by_system[key] = entry
    return sorted(by_system.values(), key=lambda e: (e.get("updatedAt") or ""), reverse=True)


def _push_undo(session: dict[str, Any]) -> None:
    # Store draft + nodes together so point deletes undo correctly
    session["undo"].append(
        {
            "draft": copy.deepcopy(session["draft"]),
            "nodes": copy.deepcopy(session.get("nodes") or []),
        }
    )
    if len(session["undo"]) > 50:
        session["undo"] = session["undo"][-50:]


def undo(session: dict[str, Any]) -> dict[str, Any]:
    if not session["undo"]:
        raise ValueError("Nothing to undo")
    item = session["undo"].pop()
    if isinstance(item, dict) and "draft" in item:
        session["draft"] = item["draft"]
        if "nodes" in item:
            session["nodes"] = item["nodes"]
    else:
        # legacy undo entries were a bare draft deepcopy
        session["draft"] = item
    save_session(session)
    return session


"""Create / open / reload review sessions."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft
from source_extract.review.draft_resolver import _resolve_draft_path, load_draft
from source_extract.review.nodes_attach import (
    _attach_nodes,
    _ensure_page_calibration,
    _read_curves_pixel_origin,
    merge_detected_isotherms,
)
from source_extract.review.session_common import _as_wt_list, _default_arrows, _now
from source_extract.review.session_image import _image_meta_for_session
from source_extract.review.session_image_refresh import (
    _attach_reference_overlay,
    _ensure_clean_session_image,
    _refresh_session_image,
)
from source_extract.review.session_persist import (
    _push_undo,
    list_sessions,
    load_session,
    save_session,
    session_path,
)
from source_extract.review.session_view import _build_view


def find_reusable_session(
    system_id: str,
    preferred_source: str | None = None,
) -> dict[str, Any] | None:
    """Latest non-confirmed session for this system.

    ``preferred_source`` is ignored for matching — one reviewing session per system —
    so switching auto-full ↔ candidates does not spawn duplicates.
    """
    del preferred_source  # reserved for callers; reuse is per-system only
    needle = system_id.lower()
    best: dict[str, Any] | None = None
    best_mtime = -1.0
    for path in RP.sessions_dir().glob("*.json"):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (s.get("systemId") or "").lower() != needle:
            continue
        if s.get("status") == "confirmed":
            continue
        # Skip legacy stub sessions (old SessionStore) without a draft payload
        if not isinstance(s.get("draft"), dict):
            continue
        mtime = path.stat().st_mtime
        if mtime > best_mtime:
            best = s
            best_mtime = mtime
    return best


def _session_keep_rank(s: dict[str, Any]) -> tuple[int, int, float]:
    """Prefer edited / content-rich reviewing sessions over empty auto-full shells."""
    from source_extract.review.draft_resolver import _draft_content_score

    draft = s.get("draft") or {}
    score = _draft_content_score(draft)
    edits = len(s.get("undo") or [])
    # updatedAt is ISO; fall back to 0
    return (edits, score, 1.0 if s.get("updatedAt") else 0.0)


def prune_duplicate_sessions(*, keep_confirmed: bool = True) -> int:
    """Keep one reviewing session per systemId (best content/edits); drop empty dups.

    Confirmed sessions are kept. Returns number deleted.
    """
    RP.ensure_dirs()
    by_system: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path in RP.sessions_dir().glob("*.json"):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = (s.get("systemId") or path.stem).lower()
        by_system.setdefault(key, []).append((path, s))

    deleted = 0
    for _key, rows in by_system.items():
        confirmed = [(p, s) for p, s in rows if s.get("status") == "confirmed"]
        reviewing = [(p, s) for p, s in rows if s.get("status") != "confirmed"]
        if keep_confirmed:
            # Only keep the newest confirmed per system as well (optional clutter control)
            confirmed.sort(key=lambda r: r[0].stat().st_mtime, reverse=True)
            for path, s in confirmed[1:]:
                try:
                    path.unlink(missing_ok=True)
                    deleted += 1
                except OSError:
                    pass

        if not reviewing:
            continue
        reviewing.sort(
            key=lambda r: (_session_keep_rank(r[1]), r[0].stat().st_mtime),
            reverse=True,
        )
        # Keep the best reviewing session; delete the rest if they have no edits
        keep_path = reviewing[0][0]
        for path, s in reviewing[1:]:
            if bool(s.get("undo")):
                continue  # preserve alternate edited drafts
            try:
                path.unlink(missing_ok=True)
                base = RP.sessions_dir() / f"{s.get('id')}.base.png"
                base.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        _ = keep_path
    return deleted


def create_session(
    system_id: str,
    preferred_source: str | None = None,
    *,
    force_new: bool = False,
) -> dict[str, Any]:
    RP.ensure_dirs()
    if not force_new:
        existing = find_reusable_session(system_id, preferred_source=preferred_source)
        if existing is not None:
            # Switching draft source (e.g. after Analyze → auto-full) must reload JSON + raster
            if preferred_source and existing.get("draftSource") != preferred_source:
                try:
                    from source_extract.review.session_public import reload_draft_from_disk

                    return reload_draft_from_disk(existing, preferred_source=preferred_source)
                except (FileNotFoundError, ValueError):
                    pass
            pixel_origin = _read_curves_pixel_origin(system_id)
            existing["pixelOrigin"] = list(pixel_origin)
            binary = is_binary_draft(existing.get("draft"))
            existing["diagramKind"] = "binary" if binary else "ternary"
            if not binary:
                _ensure_page_calibration(existing["draft"], pixel_origin)
                # Pull pd-isotherms geometry when draft isotherms still lack polylines
                if not any(iso.get("polyline_wt") for iso in existing["draft"].get("isotherms") or []):
                    merge_detected_isotherms(existing["draft"], system_id, pixel_origin)
                    comps = list(existing["draft"].get("components") or [])
                    for iso in existing["draft"].get("isotherms") or []:
                        iso["polyline_wt"] = _as_wt_list(iso.get("polyline_wt") or [], comps)
                _attach_nodes(existing)
                from source_extract.review.temperature_labels import assign_isotherm_temps_from_labels

                assign_isotherm_temps_from_labels(existing)
            else:
                dig = existing["draft"].setdefault("digitization", {})
                axes = axes_from_digitization(existing["draft"])
                if axes is not None and not isinstance(dig.get("axes"), dict):
                    dig["axes"] = axes.to_dict()
                existing["nodes"] = []
            # Re-crop to the pipeline PNG pageOrigin every open (avoids stale offsets)
            existing = _refresh_session_image(existing)
            existing["view"] = _build_view(existing)
            save_session(existing)
            return existing

    draft_kind, draft_path = _resolve_draft_path(system_id, preferred=preferred_source)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    # Ensure required containers exist (starts may be empty)
    draft.setdefault("invariantPoints", [])
    draft.setdefault("phases", draft.get("phases") or [])
    binary = is_binary_draft(draft)
    if binary:
        draft.setdefault("liquidus", [])
        dig = draft.setdefault("digitization", {})
        if "calibration" not in dig:
            dig["calibration"] = ""
        # Promote parsed axes onto the draft so later edits keep structured calibration
        axes = axes_from_digitization(draft)
        if axes is not None and not isinstance(dig.get("axes"), dict):
            dig["axes"] = axes.to_dict()
    else:
        draft.setdefault("boundaryCurves", [])
        draft.setdefault("isotherms", [])
        if "digitization" not in draft or "calibration" not in draft.get("digitization", {}):
            raise ValueError(f"Draft {draft_path} has no digitization.calibration — cannot open in review UI")

    pixel_origin = _read_curves_pixel_origin(system_id)
    if not binary:
        _ensure_page_calibration(draft, pixel_origin)
        merge_detected_isotherms(draft, system_id, pixel_origin)

    components = list(draft.get("components") or [])
    if not binary:
        # Normalize polyline points to [A,B,C] lists (auto-full isotherms use dicts)
        for bc in draft.get("boundaryCurves", []):
            bc["polyline_wt"] = _as_wt_list(bc.get("polyline_wt") or [], components)
            if "arrows" not in bc:
                path = list(bc.get("path") or [])
                bc["arrows"] = _default_arrows(path) or (["?"] if len(bc.get("polyline_wt") or []) >= 2 else [])
        for iso in draft.get("isotherms", []):
            iso["polyline_wt"] = _as_wt_list(iso.get("polyline_wt") or [], components)

    session_id = str(uuid.uuid4())
    image = _image_meta_for_session(
        system_id,
        draft,
        session_id,
        draft_kind=draft_kind,
        draft_stem=draft_path.stem,
    )
    session: dict[str, Any] = {
        "id": session_id,
        "systemId": draft_path.stem,
        "system": draft.get("system", system_id),
        "draftSource": draft_kind,
        "diagramKind": "binary" if binary else "ternary",
        "pixelOrigin": list(pixel_origin),
        "createdAt": _now(),
        "updatedAt": _now(),
        "status": "reviewing",
        "image": image,
        "draft": draft,
        "undo": [],
        "provenance": {"points": {}, "boundaries": {}, "isotherms": {}, "liquidus": {}},
        "guidance": {"cards": [], "answers": []},
    }
    if not binary:
        _attach_nodes(session, force=True)
        session = _ensure_clean_session_image(session)
        from source_extract.review.temperature_labels import assign_isotherm_temps_from_labels

        assign_isotherm_temps_from_labels(session)
    else:
        # Re-derive base from atlas page (render on demand) so binary opens show the scan
        session = _refresh_session_image(session)
    session["view"] = _build_view(session)
    save_session(session)
    return session


def set_session_image(
    session: dict[str, Any],
    *,
    image_bytes: bytes,
    page_origin: list[int] | None = None,
) -> dict[str, Any]:
    """Replace the session base image (e.g. upload a real scan crop)."""
    from io import BytesIO

    from PIL.PngImagePlugin import PngInfo

    RP.ensure_dirs()
    im = Image.open(BytesIO(image_bytes)).convert("RGB")
    dest = RP.sessions_dir() / f"{session['id']}.base.png"
    origin = page_origin
    if origin is None:
        # Keep existing origin if present; else 0,0
        origin = list(session.get("image", {}).get("pageOrigin") or [0, 0])
    info = PngInfo()
    info.add_text("pageOrigin", f"{int(origin[0])},{int(origin[1])}")
    im.save(dest, pnginfo=info)
    session["image"] = {
        "path": str(dest),
        "width": im.width,
        "height": im.height,
        "pageOrigin": [int(origin[0]), int(origin[1])],
        "synthetic": False,
    }
    save_session(session)
    return session

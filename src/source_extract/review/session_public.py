"""Reload draft from disk and shape public session JSON."""

from __future__ import annotations

import json
from typing import Any

from source_extract.review.binary_axes import axes_from_digitization, is_binary_draft
from source_extract.review.draft_resolver import _resolve_draft_path
from source_extract.review.nodes_attach import (
    _attach_nodes,
    _ensure_page_calibration,
    _read_curves_pixel_origin,
    merge_detected_isotherms,
)
from source_extract.review.session_common import _as_wt_list, _default_arrows
from source_extract.review.session_image_refresh import (
    _attach_reference_overlay,
    _refresh_session_image,
)
from source_extract.review.session_persist import _push_undo, save_session
from source_extract.review.session_view import _build_view

def reload_draft_from_disk(
    session: dict[str, Any],
    *,
    preferred_source: str | None = None,
) -> dict[str, Any]:
    """Replace session draft with the current candidates/systems/auto-full JSON on disk."""
    system_id = session["systemId"]
    draft_kind, draft_path = _resolve_draft_path(system_id, preferred=preferred_source)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft.setdefault("invariantPoints", [])
    draft.setdefault("phases", draft.get("phases") or [])
    binary = is_binary_draft(draft)
    if binary:
        draft.setdefault("liquidus", [])
        dig = draft.setdefault("digitization", {})
        if "calibration" not in dig:
            dig["calibration"] = ""
        axes = axes_from_digitization(draft)
        if axes is not None and not isinstance(dig.get("axes"), dict):
            dig["axes"] = axes.to_dict()
    else:
        draft.setdefault("boundaryCurves", [])
        draft.setdefault("isotherms", [])
        if "digitization" not in draft or "calibration" not in draft.get("digitization", {}):
            raise ValueError(f"Draft {draft_path} has no digitization.calibration")
    pixel_origin = _read_curves_pixel_origin(system_id)
    if not binary:
        _ensure_page_calibration(draft, pixel_origin)
        merge_detected_isotherms(draft, system_id, pixel_origin)
        components = list(draft.get("components") or [])
        for bc in draft.get("boundaryCurves", []):
            bc["polyline_wt"] = _as_wt_list(bc.get("polyline_wt") or [], components)
            if "arrows" not in bc:
                path = list(bc.get("path") or [])
                bc["arrows"] = _default_arrows(path) or (
                    ["?"] if len(bc.get("polyline_wt") or []) >= 2 else []
                )
        for iso in draft.get("isotherms", []):
            iso["polyline_wt"] = _as_wt_list(iso.get("polyline_wt") or [], components)

    _push_undo(session)
    session["draft"] = draft
    session["draftSource"] = draft_kind
    session["diagramKind"] = "binary" if binary else "ternary"
    session["pixelOrigin"] = list(pixel_origin)
    session["provenance"] = {"points": {}, "boundaries": {}, "isotherms": {}, "liquidus": {}}
    if not binary:
        _attach_nodes(session, force=True)
    else:
        session["nodes"] = []
    # Always rebuild raster to the new draft's pipeline pageOrigin (fixes layer offsets)
    session = _refresh_session_image(session)
    from source_extract.review.temperature_labels import assign_isotherm_temps_from_labels

    if not binary:
        assign_isotherm_temps_from_labels(session)
    session["view"] = _build_view(session)
    save_session(session)
    return session


def public_session(session: dict[str, Any]) -> dict[str, Any]:
    """API response without huge nested undo drafts."""
    from source_extract.review.export import isotherms_missing_temperature

    session = _attach_reference_overlay(session)
    has_ref = bool(session["image"].get("hasReferenceOverlay"))
    has_live = bool(session["image"].get("liveOverlayPath")) or True
    missing_iso_t = isotherms_missing_temperature(session)
    diagram_kind = session.get("diagramKind") or (
        "binary" if is_binary_draft(session.get("draft")) else "ternary"
    )
    return {
        "id": session["id"],
        "systemId": session["systemId"],
        "system": session["system"],
        "draftSource": session.get("draftSource"),
        "diagramKind": diagram_kind,
        "pixelOrigin": session.get("pixelOrigin"),
        "status": session["status"],
        "createdAt": session["createdAt"],
        "updatedAt": session["updatedAt"],
        "image": {
            "width": session["image"]["width"],
            "height": session["image"]["height"],
            "pageOrigin": session["image"]["pageOrigin"],
            "synthetic": bool(session["image"].get("synthetic")),
            "cleanScan": bool(session["image"].get("cleanScan")),
            "hasReferenceOverlay": has_ref,
            "url": f"/api/v1/review/sessions/{session['id']}/image",
            # Live render of current draft (regenerated after every edit)
            "liveOverlayUrl": f"/api/v1/review/sessions/{session['id']}/overlay.png",
            "referenceOverlayUrl": (
                f"/api/v1/review/sessions/{session['id']}/reference-overlay.png" if has_ref else None
            ),
            "referencePageOrigin": session["image"].get("referencePageOrigin"),
            "referenceSize": session["image"].get("referenceSize"),
            "hasLiveOverlay": has_live,
        },
        "components": session["draft"]["components"],
        "phases": session["draft"].get("phases", []),
        "source": session["draft"].get("source"),
        # Always rebuild so nodeIndex / control handles stay in sync after edits
        "view": _build_view(session),
        "nodeCount": len(session.get("nodes") or []),
        "lastIsothermBuild": session.pop("_lastIsothermBuild", None),
        "lastMoveNote": session.pop("_lastMoveNote", None),
        "lastRemap": session.pop("_lastRemap", None),
        "lastTemperaturePropagate": session.pop("_lastTemperaturePropagate", None),
        "lastIsothermJoin": session.pop("_lastIsothermJoin", None),
        "lastInvariantLookup": session.pop("_lastInvariantLookup", None),
        "lastInvariantReposition": session.pop("_lastInvariantReposition", None),
        "lastInvariantRestore": session.pop("_lastInvariantRestore", None),
        "lastNodesReload": session.pop("_lastNodesReload", None),
        "lastNodeEnsure": session.pop("_lastNodeEnsure", None),
        "lastContourJoin": session.pop("_lastContourJoin", None),
        "lastCalibrationMove": session.pop("_lastCalibrationMove", None),
        "lastClearUnused": session.pop("_lastClearUnused", None),
        "lastNormalizePoints": session.pop("_lastNormalizePoints", None),
        "lastAddNote": session.pop("_lastAddNote", None),
        "guidance": session.get("guidance", {"cards": [], "answers": []}),
        "undoDepth": len(session.get("undo") or []),
        "provenance": session.get("provenance"),
        "validation": {
            "canConfirm": len(missing_iso_t) == 0,
            "missingIsothermTemperatures": missing_iso_t,
        },
    }


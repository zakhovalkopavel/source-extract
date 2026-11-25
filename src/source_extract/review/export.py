"""Confirm: strip aux metadata and write confirmed system + overlay."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_extract.review import review_paths as RP
from source_extract.review.overlay_draw import render_confirmed_overlay


AUX_KEYS = {"notes", "new", "inferred"}  # keep inferred optionally? strip session-only
STRIP_FROM_POINTS = set()
STRIP_TOP_LEVEL_SESSION = {"undo", "view", "guidance", "provenance", "image", "id", "systemId", "status", "createdAt", "updatedAt"}


def _is_missing_temperature(value: Any) -> bool:
    if value is None:
        return True
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


def isotherms_missing_temperature(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Return isotherms that cannot be confirmed until temperature_C is set."""
    missing: list[dict[str, Any]] = []
    for i, iso in enumerate(session.get("draft", {}).get("isotherms") or []):
        if _is_missing_temperature(iso.get("temperature_C")):
            missing.append(
                {
                    "index": i,
                    "field": iso.get("field"),
                    "id": f"isotherm-{i}",
                }
            )
    return missing


def validate_session_for_confirm(session: dict[str, Any]) -> None:
    """Raise ValueError when the draft is not valid for dataset confirmation."""
    missing = isotherms_missing_temperature(session)
    if not missing:
        return
    labels = ", ".join(
        f"#{m['index']}" + (f" ({m['field']})" if m.get("field") else "") for m in missing[:12]
    )
    more = "" if len(missing) <= 12 else f" … +{len(missing) - 12} more"
    raise ValueError(
        f"Cannot confirm: {len(missing)} isotherm(s) lack temperature_C "
        f"({labels}{more}). Select each isotherm, set °C, and Save."
    )


def _clean_point(inv: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": inv["id"],
        "type": inv.get("type"),
        "temperature_C": inv.get("temperature_C"),
        "phases": inv.get("phases"),
        "liquid_wt": inv.get("liquid_wt"),
        "status": inv.get("status", "extracted"),
        "sources": inv.get("sources", []),
    }
    if inv.get("reaction"):
        out["reaction"] = inv["reaction"]
    return {k: v for k, v in out.items() if v is not None}


def _clean_boundary(bc: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "fields": bc.get("fields"),
        "path": bc.get("path"),
        "polyline_wt": bc.get("polyline_wt"),
    }
    if bc.get("dashed"):
        out["dashed"] = True
    arrows = bc.get("arrows")
    if arrows:
        out["arrows"] = arrows
    return out


def _clean_isotherm(iso: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "field": iso.get("field"),
        "temperature_C": iso.get("temperature_C"),
        "polyline_wt": iso.get("polyline_wt"),
    }
    if iso.get("dashed"):
        out["dashed"] = True
    if iso.get("closed"):
        out["closed"] = True
    if iso.get("part") is not None:
        out["part"] = iso["part"]
    return out


def build_confirmed_system(session: dict[str, Any]) -> dict[str, Any]:
    draft = session["draft"]
    digitization = dict(draft.get("digitization") or {})
    digitization["method"] = (
        digitization.get("method") or "auto"
    ) + "; reviewed and confirmed in source-extract review"
    digitization["confirmedAt"] = datetime.now(timezone.utc).isoformat()

    system = {
        "system": draft.get("system"),
        "components": draft.get("components"),
        "units": draft.get("units"),
        "source": draft.get("source"),
        "digitization": digitization,
        "phases": draft.get("phases"),
        "invariantPoints": [_clean_point(p) for p in draft.get("invariantPoints", [])],
        "boundaryCurves": [_clean_boundary(b) for b in draft.get("boundaryCurves", [])],
        "isotherms": [_clean_isotherm(i) for i in draft.get("isotherms", [])],
    }
    if draft.get("inversions"):
        system["inversions"] = draft["inversions"]
    return system


def confirm_session(session: dict[str, Any]) -> dict[str, Any]:
    validate_session_for_confirm(session)
    RP.ensure_dirs()
    system_id = session["systemId"]
    out_dir = RP.confirmed_dir() / system_id
    out_dir.mkdir(parents=True, exist_ok=True)

    confirmed = build_confirmed_system(session)
    json_path = out_dir / f"{system_id}.json"
    json_path.write_text(json.dumps(confirmed, indent=2) + "\n", encoding="utf-8")

    # Copy base image and draw overlay
    src_png = Path(session["image"]["path"])
    overlay_path = out_dir / f"{system_id}.overlay.png"
    render_confirmed_overlay(session, overlay_path)

    # Also keep a copy of the base crop
    if src_png.is_file():
        shutil.copy2(src_png, out_dir / f"{system_id}.base.png")

    # Persist audit sidecar (not part of clean system JSON)
    audit = {
        "sessionId": session["id"],
        "confirmedAt": datetime.now(timezone.utc).isoformat(),
        "provenance": session.get("provenance"),
        "guidance": session.get("guidance"),
    }
    (out_dir / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    session["status"] = "confirmed"
    from source_extract.review.session_persist import save_session

    save_session(session)

    return {
        "systemId": system_id,
        "directory": str(out_dir),
        "systemJson": str(json_path),
        "overlay": str(overlay_path),
        "summary": {
            "n_invariants": len(confirmed["invariantPoints"]),
            "n_boundaries": len(confirmed["boundaryCurves"]),
            "n_isotherms": len(confirmed["isotherms"]),
        },
    }

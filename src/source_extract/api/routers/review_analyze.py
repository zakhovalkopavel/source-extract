"""Analyze endpoint — submit adapter commands via SE JobRunner (no Docker shell-out)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.api.routers.review_schemas import AnalyzeBody
from source_extract.jobs.job_runner import get_runner
from source_extract.review import review_paths as RP
from source_extract.review import session as S
from source_extract.review.binary_axes import is_binary_draft
from source_extract.review.draft_resolver import _load_json, draft_content_stats

router = APIRouter(tags=["review"])


def _is_binary_system(system_id: str, adapter_id: str) -> bool:
    _ = adapter_id
    stats = draft_content_stats(system_id)
    if stats.get("diagramKind") == "binary":
        return True
    cfg = RP.dataset_dir() / "configs"
    for name in (f"{system_id}.config.json", f"{system_id}.curves.config.json"):
        path = cfg / name
        data = _load_json(path) if path.is_file() else None
        if data and len(data.get("components") or []) == 2:
            return True
    return False


def _analyze_commands(body: AnalyzeBody) -> list[tuple[str, dict[str, Any]]]:
    """Return (command_id, params) steps for ternary auto or binary extract."""
    system = body.systemId
    base: dict[str, Any] = {"system": system, "adapter_id": body.adapterId}
    if body.force:
        base["force"] = True
    if _is_binary_system(system, body.adapterId):
        return [("extract", base)]
    # Ternary: prefer single auto when available; else curves → nodes → isotherms
    auto_params = dict(base)
    if body.figure:
        auto_params["figure"] = body.figure
    if body.triangle is not None:
        auto_params["triangle"] = body.triangle
    if body.corners:
        auto_params["corners"] = body.corners
    if body.step:
        auto_params["step"] = body.step
    return [("auto", auto_params)]


@router.post("/analyze")
def start_analyze(body: AnalyzeBody) -> dict[str, Any]:
    if body.corners is not None and len(body.corners) != 3:
        raise HTTPException(400, "corners must be exactly 3 values: TOP LEFT RIGHT")
    steps = _analyze_commands(body)
    runner = get_runner()
    # Submit the primary command; follow-ups can be chained by the UI after success
    command_id, params = steps[0]
    record = runner.submit(command_id, params)
    return {
        "job": record.to_dict(),
        "pipeline": [c for c, _ in steps],
        "diagramKind": "binary" if command_id == "extract" else "ternary",
        "sessionId": body.sessionId,
        "draftStats": draft_content_stats(body.systemId),
    }


@router.post("/sessions/{session_id}/analyze-reload")
def analyze_reload(session_id: str) -> dict[str, Any]:
    """After Analyze succeeds, reload the richest draft into the open session."""
    try:
        session = S.load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        session = S.reload_draft_from_disk(session)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    draft = session.get("draft") or {}
    return {
        "session": S.public_session(session),
        "diagramKind": "binary" if is_binary_draft(draft) else "ternary",
        "draftStats": draft_content_stats(session["systemId"]),
        "imageExists": Path(session["image"]["path"]).is_file(),
    }

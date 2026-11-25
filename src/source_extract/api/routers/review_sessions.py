"""Session CRUD, images, undo, reload, guidance, confirm."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from source_extract.api.routers.review_schemas import (
    CardUpdateBody,
    CreateSessionBody,
    CreateStubBody,
    ReloadDraftBody,
)
from source_extract.review import guidance_cards
from source_extract.review import session as S
from source_extract.review.confirm_export import ConfirmExport
from source_extract.review.overlay_draw import render_overlay_image
from source_extract.review.session_image_refresh import _attach_reference_overlay

router = APIRouter(tags=["review"])


def _load(session_id: str) -> dict[str, Any]:
    try:
        return S.load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    return {"sessions": S.list_sessions()}


@router.post("/sessions")
def create_session(body: CreateSessionBody) -> dict[str, Any]:
    try:
        session = S.create_session(
            body.systemId,
            preferred_source=body.draftSource,
            force_new=body.forceNew,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return S.public_session(session)


@router.post("/systems/stub")
def create_stub(body: CreateStubBody) -> dict[str, Any]:
    try:
        return S.create_system_stub(
            system_id=body.systemId,
            components=body.components,
            system_name=body.systemName,
            figure=body.figure,
            printed_page=body.printedPage,
            pdf_page=body.pdfPage,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return S.public_session(_load(session_id))


@router.post("/sessions/{session_id}/reload-draft")
def reload_draft(session_id: str, body: ReloadDraftBody | None = None) -> dict[str, Any]:
    session = _load(session_id)
    preferred = body.draftSource if body else None
    try:
        session = S.reload_draft_from_disk(session, preferred_source=preferred)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return S.public_session(session)


@router.get("/sessions/{session_id}/image")
def session_image(session_id: str) -> FileResponse:
    path = _load(session_id)["image"]["path"]
    return FileResponse(path, media_type="image/png")


@router.get("/sessions/{session_id}/overlay.png")
def session_overlay(
    session_id: str,
    points: bool = True,
    curves: bool = True,
    arrows: bool = True,
) -> Response:
    session = _load(session_id)
    img = render_overlay_image(session, show_points=points, show_curves=curves, show_arrows=arrows)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@router.get("/sessions/{session_id}/reference-overlay.png")
def session_reference_overlay(session_id: str) -> FileResponse:
    session = _attach_reference_overlay(_load(session_id))
    path = session["image"].get("referenceOverlayPath")
    if not path or not Path(path).is_file():
        raise HTTPException(404, "No reference overlay PNG for this system")
    return FileResponse(path, media_type="image/png")


@router.post("/sessions/{session_id}/undo")
def undo_session(session_id: str) -> dict[str, Any]:
    try:
        session = S.undo(_load(session_id))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return S.public_session(session)


@router.post("/sessions/{session_id}/confirm")
def confirm(session_id: str) -> dict[str, Any]:
    session = _load(session_id)
    try:
        result = ConfirmExport.confirm(session)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **result, "session": S.public_session(S.load_session(session_id))}


@router.post("/sessions/{session_id}/guidance/refresh")
def refresh_guidance(session_id: str) -> dict[str, Any]:
    return S.public_session(guidance_cards.refresh_guidance(_load(session_id)))


@router.post("/sessions/{session_id}/guidance/cards/{card_id}")
def update_card(session_id: str, card_id: str, body: CardUpdateBody) -> dict[str, Any]:
    try:
        session = guidance_cards.update_card(
            _load(session_id),
            card_id=card_id,
            status=body.status,
            answer=body.answer,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return S.public_session(session)

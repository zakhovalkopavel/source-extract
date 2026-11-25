"""Command catalog endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.commands.command_catalog import get_catalog

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("")
def list_commands() -> list[dict[str, Any]]:
    return [c.to_dict() for c in get_catalog().list()]


@router.get("/{command_id}")
def get_command(command_id: str) -> dict[str, Any]:
    try:
        return get_catalog().get(command_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

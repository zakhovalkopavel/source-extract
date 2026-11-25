"""Adapters and sources listing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.adapters.adapter_registry import get_registry

router = APIRouter(prefix="/adapters", tags=["adapters"])


@router.get("")
def list_adapters() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for adapter in get_registry().list():
        caps = adapter.capabilities
        out.append(
            {
                "id": adapter.adapter_id,
                "displayName": adapter.display_name,
                "kinds": [k.value for k in caps.kinds],
                "commands": list(caps.commands),
                "formatIds": list(caps.format_ids),
                "hasNbsCrossCheck": caps.has_nbs_cross_check,
                "hasCompoundCatalog": caps.has_compound_catalog,
            }
        )
    return out


@router.get("/{adapter_id}/sources", tags=["sources"])
def list_sources(adapter_id: str) -> list[dict[str, Any]]:
    try:
        return get_registry().get(adapter_id).list_sources()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{adapter_id}/systems", tags=["sources"])
def list_systems(adapter_id: str, source_id: str | None = None) -> list[dict[str, Any]]:
    try:
        return get_registry().get(adapter_id).list_systems(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{adapter_id}/systems/{system_id}", tags=["sources"])
def get_system(
    adapter_id: str,
    system_id: str,
    preferred: str | None = None,
) -> dict[str, Any]:
    """Resolve the draft to open in review (path + draftSource + counts)."""
    try:
        adapter = get_registry().get(adapter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    resolve = getattr(adapter, "resolve_system", None)
    if not callable(resolve):
        raise HTTPException(status_code=404, detail="Adapter does not resolve drafts")
    try:
        return resolve(system_id, preferred=preferred)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

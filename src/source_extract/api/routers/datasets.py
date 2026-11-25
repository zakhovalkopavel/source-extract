"""Dataset current / history endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.adapters.adapter_registry import get_registry
from source_extract.versioning.dataset_store import DatasetStore
from source_extract.versioning.format_registry import FormatRegistry

router = APIRouter(tags=["datasets"])


def _store(adapter_id: str) -> DatasetStore:
    try:
        roots = get_registry().get(adapter_id).roots()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DatasetStore(roots.current, roots.history)


@router.get("/datasets/formats")
def list_formats() -> list[dict[str, Any]]:
    return [f.to_dict() for f in FormatRegistry.list_formats()]


@router.get("/history/{adapter_id}/{dataset_id}", tags=["history"])
def history_list(adapter_id: str, dataset_id: str) -> list[dict[str, Any]]:
    return _store(adapter_id).list_history(dataset_id)


@router.get("/history/{adapter_id}/{dataset_id}/diff", tags=["history"])
def history_diff(adapter_id: str, dataset_id: str, a: str, b: str) -> dict[str, Any]:
    return _store(adapter_id).diff(dataset_id, a, b)

"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from source_extract import __version__
from source_extract.adapters.adapter_registry import get_registry
from source_extract.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    adapters = [a.adapter_id for a in get_registry().list()]
    return HealthResponse(ok=True, version=__version__, adapters=adapters)

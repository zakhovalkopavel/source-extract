"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    command_id: str = Field(alias="commandId")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class OcrRegionRequest(BaseModel):
    image_path: str = Field(alias="imagePath")
    box: list[int]
    engine: str = "page-ocr"
    language: str = "eng"
    whitelist: str | None = None
    psm: int | None = None
    scale: float = 1.0
    rotate: float = 0.0
    prompt: str | None = None

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    ok: bool
    version: str
    adapters: list[str]

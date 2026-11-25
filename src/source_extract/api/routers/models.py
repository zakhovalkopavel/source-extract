"""Model profiles, OCR region, recorded calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from source_extract.api.schemas import OcrRegionRequest
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_profiles import LLM_PROFILES
from source_extract.models.ocr.ocr_region_runner import OcrRegionRunner

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/profiles")
def list_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": p.profile_id,
            "description": p.description,
            "defaultProvider": p.default_provider,
            "defaultModelEnv": p.default_model_env,
        }
        for p in LLM_PROFILES.values()
    ]


@router.get("/calls")
def list_calls(limit: int = 50) -> list[dict[str, Any]]:
    return LlmCallRecorder().list_recent(limit)


@router.post("/ocr-region")
def ocr_region(body: OcrRegionRequest) -> dict[str, Any]:
    if len(body.box) != 4:
        raise HTTPException(status_code=400, detail="box must have 4 ints")
    path = Path(body.image_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"image not found: {path}")
    box = (body.box[0], body.box[1], body.box[2], body.box[3])
    candidates = OcrRegionRunner().ocr_region(
        path,
        box,
        engine=body.engine,
        language=body.language,
        whitelist=body.whitelist,
        psm=body.psm,
        scale=body.scale,
        rotate=body.rotate,
        prompt=body.prompt,
    )
    return {"candidates": [c.to_dict() for c in candidates]}

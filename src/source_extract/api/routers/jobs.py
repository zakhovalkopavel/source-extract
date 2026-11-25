"""Async job endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from source_extract.api.schemas import JobCreateRequest
from source_extract.jobs.job_runner import get_runner
from source_extract.jobs.job_state import JobState

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("")
def create_job(body: JobCreateRequest) -> dict[str, Any]:
    record = get_runner().submit(body.command_id, body.params)
    return record.to_dict()


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        return get_runner().get(job_id).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id}") from exc


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    try:
        return get_runner().cancel(job_id).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id}") from exc


@router.get("/{job_id}/log")
def get_job_log(job_id: str) -> dict[str, Any]:
    try:
        record = get_runner().get(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id}") from exc
    return {"id": job_id, "state": record.state.value, "log": record.log_lines}


@router.get("/{job_id}/stream")
async def stream_job_log(job_id: str) -> EventSourceResponse:
    async def events() -> AsyncIterator[dict[str, str]]:
        last = 0
        while True:
            try:
                record = get_runner().get(job_id)
            except FileNotFoundError:
                yield {"event": "error", "data": json.dumps({"error": "not found"})}
                return
            lines = record.log_lines[last:]
            for line in lines:
                yield {"event": "log", "data": line}
            last = len(record.log_lines)
            if record.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
                yield {"event": "done", "data": json.dumps(record.to_dict())}
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(events())

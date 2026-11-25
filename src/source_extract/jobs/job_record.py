"""Persisted job record shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from source_extract.jobs.job_state import JobState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    """One async command run."""

    command_id: str
    params: dict[str, Any]
    job_id: str = field(default_factory=lambda: str(uuid4()))
    state: JobState = JobState.QUEUED
    exit_code: int | None = None
    error: str | None = None
    log_lines: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def append_log(self, line: str) -> None:
        self.log_lines.append(line.rstrip("\n"))
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.job_id,
            "commandId": self.command_id,
            "params": self.params,
            "state": self.state.value,
            "exitCode": self.exit_code,
            "error": self.error,
            "log": self.log_lines,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

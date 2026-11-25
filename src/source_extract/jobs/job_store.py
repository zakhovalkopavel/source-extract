"""File-backed job store under the work root."""

from __future__ import annotations

import json
import os
from pathlib import Path

from source_extract.constants.env_names import SE_WORK_ROOT
from source_extract.jobs.job_record import JobRecord
from source_extract.jobs.job_state import JobState


class JobStore:
    """Persist JobRecord JSON files."""

    def __init__(self, root: Path | None = None) -> None:
        env = os.environ.get(SE_WORK_ROOT, "reports/source-extract")
        self._root = (root or Path(env)) / "jobs"
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, record: JobRecord) -> None:
        path = self._root / f"{record.job_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

    def load(self, job_id: str) -> JobRecord:
        path = self._root / f"{job_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        record = JobRecord(
            job_id=data["id"],
            command_id=data["commandId"],
            params=data.get("params") or {},
            state=JobState(data["state"]),
            exit_code=data.get("exitCode"),
            error=data.get("error"),
            log_lines=list(data.get("log") or []),
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", ""),
        )
        return record

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self._root.glob("*.json"))

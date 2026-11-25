"""In-process async job runner (thread pool; no Docker shell-out)."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from source_extract.commands.command_catalog import get_catalog
from source_extract.jobs.job_record import JobRecord
from source_extract.jobs.job_state import JobState
from source_extract.jobs.job_store import JobStore


class JobRunner:
    """Submit CommandSpec runs and persist logs via JobRecord."""

    def __init__(self, store: JobStore | None = None, max_workers: int = 2) -> None:
        self._store = store or JobStore()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="se-job")
        self._cancel: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[int]] = {}

    def submit(self, command_id: str, params: dict[str, Any]) -> JobRecord:
        record = JobRecord(command_id=command_id, params=params)
        self._store.save(record)
        cancel = threading.Event()
        self._cancel[record.job_id] = cancel
        future = self._pool.submit(self._run, record.job_id, cancel)
        self._futures[record.job_id] = future
        return record

    def get(self, job_id: str) -> JobRecord:
        return self._store.load(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        event = self._cancel.get(job_id)
        if event is not None:
            event.set()
        record = self._store.load(job_id)
        if record.state in {JobState.QUEUED, JobState.RUNNING}:
            record.state = JobState.CANCELLED
            record.touch()
            self._store.save(record)
        return record

    def _run(self, job_id: str, cancel: threading.Event) -> int:
        record = self._store.load(job_id)
        if cancel.is_set():
            record.state = JobState.CANCELLED
            self._store.save(record)
            return 130
        record.state = JobState.RUNNING
        record.append_log(f"Starting {record.command_id}")
        self._store.save(record)

        def log_append(line: str) -> None:
            record.append_log(line)
            self._store.save(record)

        try:
            spec = get_catalog().get(record.command_id)
            params = dict(record.params)
            params["_log_append"] = log_append
            code = spec.execute(params)
            if cancel.is_set():
                record.state = JobState.CANCELLED
            elif code == 0:
                record.state = JobState.SUCCEEDED
            else:
                record.state = JobState.FAILED
            record.exit_code = code
            record.append_log(f"Finished with exit code {code}")
        except Exception as exc:  # noqa: BLE001 — surface to job record
            record.state = JobState.FAILED
            record.exit_code = 1
            record.error = str(exc)
            record.append_log(f"ERROR: {exc}")
        self._store.save(record)
        return record.exit_code if record.exit_code is not None else 1


_RUNNER: JobRunner | None = None


def get_runner() -> JobRunner:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = JobRunner()
    return _RUNNER

"""Job lifecycle states."""

from __future__ import annotations

from enum import Enum


class JobState(str, Enum):
    """Async job status values."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

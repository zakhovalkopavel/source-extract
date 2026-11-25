"""Filesystem roots for review sessions (adapter / env — no host brand strings)."""

from __future__ import annotations

import os
from pathlib import Path

from source_extract.constants.env_names import SE_DATASET_ROOT, SE_HISTORY_ROOT, SE_WORK_ROOT


def work_dir() -> Path:
    return Path(os.environ.get(SE_WORK_ROOT, "reports/source-extract"))


def dataset_dir() -> Path:
    return Path(os.environ.get(SE_DATASET_ROOT, "shared/processed/phase-diagrams"))


def history_dir() -> Path:
    return Path(os.environ.get(SE_HISTORY_ROOT, "reports/source-extract/history"))


def data_dir() -> Path:
    """Writable review-local data under the work root."""
    return work_dir() / "review-data"


def sessions_dir() -> Path:
    return work_dir() / "review-sessions"


def confirmed_dir() -> Path:
    return data_dir() / "confirmed"


def auto_full_dir() -> Path:
    return work_dir() / "auto-full"


def repo_root() -> Path:
    """Best-effort repo root (optional; used only for page PDF renders)."""
    env = os.environ.get("SE_REPO_ROOT")
    if env:
        return Path(env)
    # vendor/source-extract/src/source_extract/review → up to repo
    return Path(__file__).resolve().parents[5]


def draft_search_roots() -> list[tuple[str, Path]]:
    """Ordered (kind, path) pairs for draft JSON discovery."""
    return [
        ("auto-full", auto_full_dir()),
        ("candidates", work_dir() / "candidates"),
        ("systems", dataset_dir() / "systems"),
        ("starts", work_dir() / "starts"),
        ("review-starts", data_dir() / "starts"),
    ]


def ensure_dirs() -> None:
    sessions_dir().mkdir(parents=True, exist_ok=True)
    confirmed_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / "jobs").mkdir(parents=True, exist_ok=True)
    (data_dir() / "starts").mkdir(parents=True, exist_ok=True)

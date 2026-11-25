"""RunRecorder port — Postgres implementation lands in the next plan."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from source_extract.versioning.run_manifest import RunManifest


@runtime_checkable
class RunRecorder(Protocol):
    """Persist run manifests (file today, database next plan)."""

    def record(self, manifest: RunManifest) -> Path:
        """Write the manifest and return its path."""

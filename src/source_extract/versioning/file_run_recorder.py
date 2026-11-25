"""File-backed RunRecorder implementation."""

from __future__ import annotations

import json
from pathlib import Path

from source_extract.versioning.run_manifest import RunManifest


class FileRunRecorder:
    """JSON files under ``history/manifests/``."""

    def __init__(self, history_root: Path) -> None:
        self._dir = history_root / "manifests"
        self._dir.mkdir(parents=True, exist_ok=True)

    def record(self, manifest: RunManifest) -> Path:
        path = self._dir / f"{manifest.manifest_id}.json"
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return path

"""current / history filesystem store with atomic promote."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_extract.versioning.file_run_recorder import FileRunRecorder
from source_extract.versioning.format_registry import SYSTEM_JSON_V1, FormatRegistry
from source_extract.versioning.run_manifest import RunManifest


class DatasetStore:
    """Move previous current into history and write a new current + manifest."""

    def __init__(self, current_root: Path, history_root: Path) -> None:
        self.current_root = current_root
        self.history_root = history_root
        self.history_root.mkdir(parents=True, exist_ok=True)
        self._recorder = FileRunRecorder(history_root)

    def archive_current(self, *, relative_path: str, dataset_id: str) -> str | None:
        """Copy the current file into history; return the history version id."""
        dest = self.current_root / relative_path
        if not dest.is_file():
            return None
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = self.history_root / dataset_id / version
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, archive_dir / dest.name)
        return version

    def promote_file(
        self,
        *,
        relative_path: str,
        source_path: Path,
        dataset_id: str,
        command: str,
        parameters: dict[str, Any] | None = None,
        adapter_id: str = "",
    ) -> RunManifest:
        """Copy ``source_path`` into current; archive prior file under history."""
        previous_version = self.archive_current(relative_path=relative_path, dataset_id=dataset_id)
        dest = self.current_root / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(source_path, dest)
        fmt = SYSTEM_JSON_V1
        manifest = RunManifest(
            dataset_id=dataset_id,
            version=version,
            previous_version=previous_version,
            command=command,
            parameters=parameters or {},
            adapter_id=adapter_id,
            format_block=fmt.to_dict(),
            change_note=FormatRegistry.change_note(fmt.format_id, fmt.version),
            input_hashes={"source": self.hash_file(source_path)},
            diff_summary={"promoted": relative_path},
        )
        self._recorder.record(manifest)
        return manifest

    def list_history(self, dataset_id: str) -> list[dict[str, Any]]:
        root = self.history_root / dataset_id
        if not root.is_dir():
            return []
        return [{"version": p.name, "path": str(p)} for p in sorted(root.iterdir()) if p.is_dir()]

    def diff(self, dataset_id: str, version_a: str, version_b: str) -> dict[str, Any]:
        """Shallow file presence / size diff between two history versions."""
        a = self.history_root / dataset_id / version_a
        b = self.history_root / dataset_id / version_b
        files_a = {p.name: p.stat().st_size for p in a.glob("*")} if a.is_dir() else {}
        files_b = {p.name: p.stat().st_size for p in b.glob("*")} if b.is_dir() else {}
        return {
            "added": sorted(set(files_b) - set(files_a)),
            "removed": sorted(set(files_a) - set(files_b)),
            "changed": sorted(
                name for name in set(files_a) & set(files_b) if files_a[name] != files_b[name]
            ),
        }

    def prune_accepted(self, dataset_id: str) -> int:
        """Remove all history versions for a dataset once quality is accepted."""
        root = self.history_root / dataset_id
        if not root.is_dir():
            return 0
        count = sum(1 for _ in root.iterdir())
        shutil.rmtree(root)
        return count

    @staticmethod
    def hash_file(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()[:16]

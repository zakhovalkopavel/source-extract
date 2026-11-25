"""File-backed review session metadata (split from diagram-review session)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from source_extract.constants.env_names import SE_WORK_ROOT


class SessionStore:
    """CRUD for review session JSON files."""

    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(os.environ.get(SE_WORK_ROOT, "reports/source-extract"))
        self._dir = base / "review-sessions"
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(self, system_id: str, draft_path: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        session_id = str(uuid4())
        record = {
            "id": session_id,
            "systemId": system_id,
            "draftPath": draft_path,
            "meta": meta or {},
            "edits": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        self._write(session_id, record)
        return record

    def get(self, session_id: str) -> dict[str, Any]:
        return json.loads((self._dir / f"{session_id}.json").read_text(encoding="utf-8"))

    def list(self) -> list[dict[str, Any]]:
        return [self.get(p.stem) for p in sorted(self._dir.glob("*.json"))]

    def append_edit(self, session_id: str, edit: dict[str, Any]) -> dict[str, Any]:
        record = self.get(session_id)
        record["edits"].append(edit)
        record["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self._write(session_id, record)
        return record

    def _write(self, session_id: str, record: dict[str, Any]) -> None:
        (self._dir / f"{session_id}.json").write_text(
            json.dumps(record, indent=2),
            encoding="utf-8",
        )

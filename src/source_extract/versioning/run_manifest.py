"""Run manifest written on every promote / dataset write."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunManifest:
    """Metadata for one dataset write."""

    dataset_id: str
    version: str
    command: str
    previous_version: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    models: list[dict[str, Any]] = field(default_factory=list)
    adapter_id: str = ""
    adapter_version: str = ""
    source_refs: list[str] = field(default_factory=list)
    input_hashes: dict[str, str] = field(default_factory=dict)
    diff_summary: dict[str, Any] = field(default_factory=dict)
    format_block: dict[str, Any] = field(default_factory=dict)
    change_note: str = ""
    manifest_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.manifest_id,
            "datasetId": self.dataset_id,
            "version": self.version,
            "previousVersion": self.previous_version,
            "command": self.command,
            "parameters": self.parameters,
            "models": self.models,
            "adapterId": self.adapter_id,
            "adapterVersion": self.adapter_version,
            "sourceRefs": self.source_refs,
            "inputHashes": self.input_hashes,
            "diffSummary": self.diff_summary,
            "format": self.format_block,
            "changeNote": self.change_note,
            "createdAt": self.created_at,
        }

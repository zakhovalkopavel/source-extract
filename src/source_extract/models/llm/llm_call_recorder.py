"""Record every LLM call for later database persistence."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from source_extract.constants.env_names import SE_WORK_ROOT
from source_extract.models.llm.llm_response import LlmResponse


class LlmCallRecorder:
    """Append JSON records under work/llm-calls/."""

    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(os.environ.get(SE_WORK_ROOT, "reports/source-extract"))
        self._dir = base / "llm-calls"
        self._dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        prompt_template_id: str,
        rendered_prompt: str,
        provider: str,
        model: str,
        parameters: dict[str, Any],
        response: LlmResponse,
    ) -> Path:
        payload = {
            "id": str(uuid4()),
            "promptTemplateId": prompt_template_id,
            "renderedPrompt": rendered_prompt,
            "provider": provider,
            "model": model,
            "parameters": parameters,
            "promptTokens": response.prompt_tokens,
            "completionTokens": response.completion_tokens,
            "latencyMs": response.latency_ms,
            "responseHash": response.response_hash
            or hashlib.sha256(response.text.encode()).hexdigest()[:16],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        path = self._dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[dict[str, Any]] = []
        for path in files[:limit]:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        return out

"""Anthropic LlmClient adapter (optional dependency)."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from source_extract.constants.env_names import SE_LLM_API_KEY, SE_LLM_MODEL
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_message import LlmMessage
from source_extract.models.llm.llm_response import LlmResponse


class AnthropicLlmClient:
    """Claude via anthropic SDK when installed."""

    def __init__(self, recorder: LlmCallRecorder | None = None) -> None:
        self._recorder = recorder or LlmCallRecorder()
        self._api_key = os.environ.get(SE_LLM_API_KEY) or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = os.environ.get(SE_LLM_MODEL, "")

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        profile: str | None = None,
    ) -> LlmResponse:
        if not self._api_key:
            raise RuntimeError("Anthropic API key is not set")
        if not self._model:
            raise RuntimeError(f"{SE_LLM_MODEL} is not set")
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("Install anthropic (pip install 'source-extract[llm-anthropic]')") from exc

        started = time.perf_counter()
        client = anthropic.Anthropic(api_key=self._api_key)
        payload = [{"role": m.role if m.role != "system" else "user", "content": m.content} for m in messages]
        result = client.messages.create(model=self._model, max_tokens=2048, messages=payload)
        body = "".join(block.text for block in result.content if getattr(block, "type", "") == "text")
        response = LlmResponse(
            text=body,
            provider="anthropic",
            model=self._model,
            latency_ms=(time.perf_counter() - started) * 1000,
            response_hash=hashlib.sha256(body.encode()).hexdigest()[:16],
        )
        self._recorder.record(
            prompt_template_id=profile or "raw",
            rendered_prompt="\n".join(f"{m.role}: {m.content}" for m in messages),
            provider="anthropic",
            model=self._model,
            parameters={"tools": bool(tools), "jsonSchema": bool(json_schema)},
            response=response,
        )
        return response

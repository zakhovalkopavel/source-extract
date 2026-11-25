"""OpenAI + OpenAI-compatible (Ollama / llama.cpp) LlmClient stub."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from source_extract.constants.env_names import SE_LLM_API_KEY, SE_LLM_MODEL
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_message import LlmMessage
from source_extract.models.llm.llm_response import LlmResponse


class OpenAiCompatibleClient:
    """Uses the openai package when installed."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        recorder: LlmCallRecorder | None = None,
        provider_name: str = "openai",
    ) -> None:
        self._base_url = base_url or os.environ.get("SE_LLM_BASE_URL")
        self._api_key = os.environ.get(SE_LLM_API_KEY) or os.environ.get("OPENAI_API_KEY", "")
        self._model = os.environ.get(SE_LLM_MODEL, "")
        self._recorder = recorder or LlmCallRecorder()
        self._provider_name = provider_name

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        profile: str | None = None,
    ) -> LlmResponse:
        if not self._model:
            raise RuntimeError(f"{SE_LLM_MODEL} is not set")
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("Install openai (pip install 'source-extract[llm-openai]')") from exc

        started = time.perf_counter()
        client = OpenAI(api_key=self._api_key or "unused", base_url=self._base_url)
        payload = [{"role": m.role, "content": m.content} for m in messages]
        kwargs: dict[str, Any] = {"model": self._model, "messages": payload}
        if tools:
            kwargs["tools"] = tools
        completion = client.chat.completions.create(**kwargs)
        body = completion.choices[0].message.content or ""
        usage = getattr(completion, "usage", None)
        response = LlmResponse(
            text=body,
            provider=self._provider_name,
            model=self._model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=(time.perf_counter() - started) * 1000,
            response_hash=hashlib.sha256(body.encode()).hexdigest()[:16],
        )
        rendered = "\n".join(f"{m.role}: {m.content}" for m in messages)
        self._recorder.record(
            prompt_template_id=profile or "raw",
            rendered_prompt=rendered,
            provider=self._provider_name,
            model=self._model,
            parameters={"jsonSchema": bool(json_schema)},
            response=response,
        )
        return response

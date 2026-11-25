"""Google (Gemini) LlmClient adapter."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from source_extract.constants.env_names import SE_LLM_API_KEY, SE_LLM_MODEL
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_message import LlmMessage
from source_extract.models.llm.llm_response import LlmResponse


class GoogleLlmClient:
    """Gemini via google-genai when installed; otherwise a clear error."""

    def __init__(self, recorder: LlmCallRecorder | None = None) -> None:
        self._recorder = recorder or LlmCallRecorder()
        self._api_key = os.environ.get(SE_LLM_API_KEY) or os.environ.get("GOOGLE_API_KEY", "")
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
            raise RuntimeError(f"{SE_LLM_API_KEY} (or GOOGLE_API_KEY) is not set")
        if not self._model:
            raise RuntimeError(f"{SE_LLM_MODEL} is not set — confirm the id against the provider listing")
        started = time.perf_counter()
        try:
            from google import genai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("Install google-genai (pip install 'source-extract[llm-google]')") from exc

        client = genai.Client(api_key=self._api_key)
        # Flatten to a single user prompt for the scaffold; full multi-turn later.
        text = "\n".join(f"{m.role}: {m.content}" for m in messages)
        config: dict[str, Any] = {}
        if json_schema is not None:
            config["response_mime_type"] = "application/json"
        result = client.models.generate_content(model=self._model, contents=text, config=config or None)
        body = getattr(result, "text", None) or str(result)
        latency = (time.perf_counter() - started) * 1000
        response = LlmResponse(
            text=body,
            provider="google",
            model=self._model,
            latency_ms=latency,
            response_hash=hashlib.sha256(body.encode()).hexdigest()[:16],
        )
        self._recorder.record(
            prompt_template_id=profile or "raw",
            rendered_prompt=text,
            provider="google",
            model=self._model,
            parameters={"tools": bool(tools), "jsonSchema": bool(json_schema)},
            response=response,
        )
        return response

"""Build an LlmClient from SE_LLM_PROVIDER."""

from __future__ import annotations

import os

from source_extract.constants.env_names import SE_LLM_PROVIDER
from source_extract.models.llm.anthropic_llm_client import AnthropicLlmClient
from source_extract.models.llm.google_llm_client import GoogleLlmClient
from source_extract.models.llm.llm_call_recorder import LlmCallRecorder
from source_extract.models.llm.llm_client import LlmClient
from source_extract.models.llm.openai_compatible_client import OpenAiCompatibleClient


class LlmClientFactory:
    """Provider selection from environment."""

    @staticmethod
    def create(provider: str | None = None, recorder: LlmCallRecorder | None = None) -> LlmClient:
        name = (provider or os.environ.get(SE_LLM_PROVIDER, "google")).lower()
        rec = recorder or LlmCallRecorder()
        if name in {"google", "gemini"}:
            return GoogleLlmClient(recorder=rec)
        if name in {"openai"}:
            return OpenAiCompatibleClient(recorder=rec, provider_name="openai")
        if name in {"openai_compatible", "ollama", "local"}:
            return OpenAiCompatibleClient(recorder=rec, provider_name="openai_compatible")
        if name in {"anthropic", "claude"}:
            return AnthropicLlmClient(recorder=rec)
        raise ValueError(f"Unknown LLM provider: {name}")

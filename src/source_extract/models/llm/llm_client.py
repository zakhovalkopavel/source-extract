"""LlmClient protocol — provider-agnostic."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from source_extract.models.llm.llm_message import LlmMessage
from source_extract.models.llm.llm_response import LlmResponse


@runtime_checkable
class LlmClient(Protocol):
    """Chat, structured JSON, tool calling, vision."""

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        profile: str | None = None,
    ) -> LlmResponse:
        """Run a completion."""

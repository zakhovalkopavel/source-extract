"""Structured response from an LlmClient call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmResponse:
    """Provider-agnostic completion result."""

    text: str
    structured: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    response_hash: str = ""

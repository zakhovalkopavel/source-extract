"""Chat message shape for LlmClient."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LlmMessage:
    """One chat turn (text and optional image bytes / mime)."""

    role: str
    content: str
    images: list[tuple[bytes, str]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    raw: dict[str, Any] | None = None

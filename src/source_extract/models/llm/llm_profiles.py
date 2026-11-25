"""Named LLM profiles — commands ask for a profile, not a vendor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmProfile:
    """Logical profile mapped to provider/model via env/config."""

    profile_id: str
    description: str
    default_provider: str
    default_model_env: str


LLM_PROFILES: dict[str, LlmProfile] = {
    "fast-assist": LlmProfile(
        profile_id="fast-assist",
        description="Fast assistant for proposals and guidance",
        default_provider="google",
        default_model_env="SE_LLM_MODEL",
    ),
    "vision-check": LlmProfile(
        profile_id="vision-check",
        description="Vision checks on diagram crops",
        default_provider="google",
        default_model_env="SE_LLM_MODEL",
    ),
    "local-ocr-helper": LlmProfile(
        profile_id="local-ocr-helper",
        description="OpenAI-compatible local helper",
        default_provider="openai_compatible",
        default_model_env="SE_LLM_MODEL",
    ),
}

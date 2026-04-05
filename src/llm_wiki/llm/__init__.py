from __future__ import annotations

from pathlib import Path

from .base import LLMProvider, LLMUnavailableError
from .config import LLMSettings, load_llm_settings
from .providers.gemini import GeminiProvider


def get_llm_provider(
    *,
    base_path: Path,
    provider_name: str | None = None,
    model: str | None = None,
) -> LLMProvider | None:
    settings = load_llm_settings(base_path=base_path, provider=provider_name, model=model)
    if not settings.enabled or settings.provider is None:
        return None
    if settings.provider == "gemini":
        return GeminiProvider(settings)
    raise LLMUnavailableError(f"Unsupported LLM provider: {settings.provider}")


__all__ = ["LLMProvider", "LLMSettings", "LLMUnavailableError", "get_llm_provider", "load_llm_settings"]

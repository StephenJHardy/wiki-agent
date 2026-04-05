from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT_SECONDS = 30.0


class LLMSettings(BaseModel):
    provider: str | None = None
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    temperature: float = DEFAULT_TEMPERATURE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    enabled: bool = False


def load_llm_settings(
    *,
    base_path: Path,
    provider: str | None = None,
    model: str | None = None,
) -> LLMSettings:
    dotenv_values = load_dotenv(base_path / ".env")
    merged = {**dotenv_values, **os.environ}

    selected_provider = provider or merged.get("LLM_WIKI_PROVIDER")
    api_key = merged.get("GOOGLE_API_KEY") or merged.get("GEMINI_API_KEY")
    if selected_provider is None and api_key:
        selected_provider = DEFAULT_PROVIDER

    selected_model = model or merged.get("LLM_WIKI_MODEL") or DEFAULT_MODEL
    temperature = parse_float(merged.get("LLM_WIKI_TEMPERATURE"), DEFAULT_TEMPERATURE)
    timeout_seconds = parse_float(merged.get("LLM_WIKI_TIMEOUT_SECONDS"), DEFAULT_TIMEOUT_SECONDS)

    enabled = bool(selected_provider and api_key)
    return LLMSettings(
        provider=selected_provider,
        model=selected_model,
        api_key=api_key,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        enabled=enabled,
    )


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = strip_quotes(value.strip())
    return values


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default

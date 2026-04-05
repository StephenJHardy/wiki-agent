from __future__ import annotations

from pathlib import Path

from llm_wiki.llm.config import load_llm_settings


def test_load_llm_settings_from_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GOOGLE_API_KEY=test-key",
                "LLM_WIKI_PROVIDER=gemini",
                "LLM_WIKI_MODEL=gemini-test-model",
                "LLM_WIKI_TEMPERATURE=0.2",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_llm_settings(base_path=tmp_path)

    assert settings.enabled is True
    assert settings.provider == "gemini"
    assert settings.model == "gemini-test-model"
    assert settings.temperature == 0.2

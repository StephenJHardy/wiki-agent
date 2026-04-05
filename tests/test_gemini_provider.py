from __future__ import annotations

from types import SimpleNamespace

from llm_wiki.llm.config import LLMSettings
from llm_wiki.llm.providers.gemini import GeminiProvider
from llm_wiki.llm.schemas import StructuredQuerySynthesis


class FakeModels:
    def __init__(self, parsed: object) -> None:
        self._parsed = parsed

    def generate_content(self, **_: object) -> object:
        return SimpleNamespace(parsed=self._parsed, text="")


class FakeClient:
    def __init__(self, parsed: object) -> None:
        self.models = FakeModels(parsed)


def test_gemini_provider_validates_structured_payload() -> None:
    provider = GeminiProvider(
        LLMSettings(provider="gemini", model="gemini-test", api_key="test", enabled=True),
        client=FakeClient(
            {
                "answer": "Retrieval helps when current knowledge is needed.",
                "uncertainty_notes": ["Coverage is limited."],
                "follow_up_questions": ["Which sources support this most strongly?"],
            }
        ),
    )

    result = provider.generate_structured(
        prompt="test",
        schema=StructuredQuerySynthesis,
        system_instruction="test",
    )

    assert result.answer.startswith("Retrieval helps")
    assert result.uncertainty_notes == ["Coverage is limited."]

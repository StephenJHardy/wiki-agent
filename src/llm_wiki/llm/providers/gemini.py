from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..base import LLMInvocationError
from ..config import LLMSettings
from ..retry import retry_call


class GeminiProvider:
    def __init__(self, settings: LLMSettings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or genai.Client(api_key=settings.api_key)

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        def invoke() -> Any:
            return self.client.models.generate_content(
                model=self.settings.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=self.settings.temperature if temperature is None else temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

        try:
            response = retry_call(invoke)
        except Exception as exc:  # noqa: BLE001
            raise LLMInvocationError(f"Gemini invocation failed: {exc}") from exc

        parsed = getattr(response, "parsed", None)
        if parsed is None:
            text = getattr(response, "text", "")
            if not text:
                raise LLMInvocationError("Gemini returned no parsed payload and no text fallback.")
            return schema.model_validate_json(text)
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate(parsed)

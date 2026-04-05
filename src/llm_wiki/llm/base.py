from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMError(RuntimeError):
    """Base error for provider-backed LLM operations."""


class LLMUnavailableError(LLMError):
    """Raised when a provider cannot be initialized."""


class LLMInvocationError(LLMError):
    """Raised when a provider call fails or returns unusable output."""


class LLMProvider(Protocol):
    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[SchemaT],
        system_instruction: str | None = None,
        temperature: float | None = None,
    ) -> SchemaT: ...

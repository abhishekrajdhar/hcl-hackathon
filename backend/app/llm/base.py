"""Provider-agnostic LLM transport.

`LLMProvider` is the seam the task calls for: swap Claude for OpenAI for a mock
without touching any caller. Providers only move text/JSON in and out — they do
not know about profiles, and they never write to the database. Concrete
providers live in `app.llm.providers`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    text: str
    provider: str
    model: str
    raw: dict[str, Any] | None = None


class LLMError(Exception):
    """Base for provider transport failures (network, auth, missing SDK)."""


class LLMProvider(ABC):
    """A text-in / text-out language-model backend.

    `complete` returns the model's raw response text — expected to be JSON when
    a `json_schema` is supplied. Parsing, validation and repair are the caller's
    responsibility, so robustness lives in one place regardless of provider.
    """

    name: str = "abstract"

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMCompletion:
        """Return the model completion. Must not raise for a merely-malformed
        model answer (that is the caller's problem); raise `LLMError` only for
        transport/auth/configuration failures."""
        raise NotImplementedError

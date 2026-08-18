"""OpenAI-compatible provider.

Works against OpenAI and any OpenAI-compatible endpoint via `OPENAI_BASE_URL`.
The `openai` SDK is imported lazily. JSON is requested with response_format
json_object; the caller still validates, so a non-conforming answer degrades to
the normal repair path rather than crashing.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.llm.base import LLMCompletion, LLMError, LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self, api_key: str | None = None, model: str | None = None, base_url: str | None = None
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_MODEL
        self._base_url = base_url or settings.OPENAI_BASE_URL

    @property
    def model(self) -> str:
        return self._model

    def _client(self) -> Any:
        if not self._api_key:
            raise LLMError(
                "OPENAI_API_KEY is not set; configure it or use LLM_PROVIDER=mock"
            )
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise LLMError(
                "The 'openai' package is not installed; add it or use LLM_PROVIDER=mock"
            ) from exc
        return openai.AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMCompletion:
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            return LLMCompletion(text=text, provider=self.name, model=self._model)
        except Exception as exc:  # pragma: no cover - network/SDK failures
            raise LLMError(f"OpenAI request failed: {exc}") from exc

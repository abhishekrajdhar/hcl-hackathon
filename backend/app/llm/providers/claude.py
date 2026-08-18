"""Anthropic Claude provider.

The `anthropic` SDK is imported lazily so the application (and every other
provider) runs without it installed; selecting this provider without the SDK or
an API key fails loudly with a clear message rather than at import time.
Structured output is obtained via a forced tool call whose input schema is the
extraction schema, which is the most reliable way to get valid JSON from Claude.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.llm.base import LLMCompletion, LLMError, LLMProvider


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._model = model or settings.ANTHROPIC_MODEL

    @property
    def model(self) -> str:
        return self._model

    def _client(self) -> Any:
        if not self._api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set; configure it or use LLM_PROVIDER=mock"
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise LLMError(
                "The 'anthropic' package is not installed; add it or use LLM_PROVIDER=mock"
            ) from exc
        return anthropic.AsyncAnthropic(api_key=self._api_key, timeout=settings.LLM_TIMEOUT_SECONDS)

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
        try:
            if json_schema is not None:
                tool = {
                    "name": "record_profile",
                    "description": "Record the structured profile extracted from the message.",
                    "input_schema": json_schema,
                }
                message = await client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": "record_profile"},
                    messages=[{"role": "user", "content": user}],
                )
                for block in message.content:
                    if getattr(block, "type", None) == "tool_use":
                        return LLMCompletion(
                            text=json.dumps(block.input),
                            provider=self.name,
                            model=self._model,
                        )
                raise LLMError("Claude did not return the expected tool call")

            message = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", None) == "text"
            )
            return LLMCompletion(text=text, provider=self.name, model=self._model)
        except LLMError:
            raise
        except Exception as exc:  # pragma: no cover - network/SDK failures
            raise LLMError(f"Claude request failed: {exc}") from exc

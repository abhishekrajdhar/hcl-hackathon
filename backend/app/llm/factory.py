"""Provider selection.

The provider is chosen from settings (env), never hard-coded in callers. The
result is cached per-process. `mock` is always available; `claude`/`openai`
validate their credentials lazily when first called, so an unconfigured
non-mock provider fails at call time with a clear message rather than at import.
"""

from __future__ import annotations

import functools

from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai import OpenAIProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    "mock": MockProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def build_provider(name: str) -> LLMProvider:
    provider_cls = _REGISTRY.get(name.lower())
    if provider_cls is None:
        raise ValueError(f"Unknown LLM provider '{name}'. Choose one of {sorted(_REGISTRY)}.")
    return provider_cls()


@functools.lru_cache
def get_llm_provider() -> LLMProvider:
    """The configured provider (settings.LLM_PROVIDER)."""
    return build_provider(settings.LLM_PROVIDER)

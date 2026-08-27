"""Provider selection.

The provider is chosen from settings (env), never hard-coded in callers. The
result is cached per-process. `mock` is always available; `claude`/`openai`
validate their credentials lazily when first called, so an unconfigured
non-mock provider fails at call time with a clear message rather than at import.

One substitution is applied on the way: asking for `openai` without an
`OPENAI_API_KEY` uses Claude instead when an `ANTHROPIC_API_KEY` is available.
The operator asked for a real model and has the credentials for one — refusing
to answer because it is the *other* real model would be pedantry. The swap is
logged, and `/health` reports the provider actually in use, so it is never
silent. With neither key set, the lazy call-time failure stands unchanged.
"""

from __future__ import annotations

import functools

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai import OpenAIProvider

logger = get_logger(__name__)

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


def resolve_provider_name(name: str) -> str:
    """The provider that will actually serve requests for this setting."""
    key = name.lower()
    if key == "openai" and not settings.OPENAI_API_KEY and settings.ANTHROPIC_API_KEY:
        logger.warning(
            "LLM_PROVIDER=openai but OPENAI_API_KEY is not set; using claude "
            "instead because ANTHROPIC_API_KEY is configured"
        )
        return "claude"
    return key


@functools.lru_cache
def get_llm_provider() -> LLMProvider:
    """The configured provider (settings.LLM_PROVIDER)."""
    return build_provider(resolve_provider_name(settings.LLM_PROVIDER))

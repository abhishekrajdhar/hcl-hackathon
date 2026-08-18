"""LLM abstraction layer: swappable providers and structured-output schemas."""

from app.llm.base import LLMCompletion, LLMError, LLMProvider
from app.llm.factory import build_provider, get_llm_provider
from app.llm.schemas import ExtractedSkill, ProfileExtraction, extraction_json_schema

__all__ = [
    "ExtractedSkill",
    "LLMCompletion",
    "LLMError",
    "LLMProvider",
    "ProfileExtraction",
    "build_provider",
    "extraction_json_schema",
    "get_llm_provider",
]

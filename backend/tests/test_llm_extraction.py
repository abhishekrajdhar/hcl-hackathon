"""Unit tests for the LLM abstraction and extraction robustness.

No network and no database: the MockProvider stands in for the model, and the
JSON/validation paths are exercised directly.
"""

from __future__ import annotations

import pytest

from app.llm.base import LLMProvider
from app.llm.factory import build_provider, get_llm_provider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.schemas import ProfileExtraction, extraction_json_schema

EXAMPLE = (
    "I am a second-year student. I know Python well and have built two machine "
    "learning projects using scikit-learn. I want to become a computer vision "
    "engineer. I can study around 10 hours per week."
)


# --- JSON extraction -------------------------------------------------------
def test_extract_plain_object() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_from_markdown_fence() -> None:
    assert extract_json_object('```json\n{"goal": "x"}\n```') == {"goal": "x"}


def test_extract_from_surrounding_prose() -> None:
    text = 'Sure, here it is: {"goal": "x", "nested": {"k": 2}} — hope that helps!'
    assert extract_json_object(text) == {"goal": "x", "nested": {"k": 2}}


def test_extract_handles_braces_in_strings() -> None:
    assert extract_json_object('{"note": "a } brace"}') == {"note": "a } brace"}


def test_extract_rejects_non_json() -> None:
    with pytest.raises(JsonExtractionError):
        extract_json_object("no json here")


def test_extract_rejects_empty() -> None:
    with pytest.raises(JsonExtractionError):
        extract_json_object("   ")


# --- factory / provider selection ------------------------------------------
def test_factory_builds_each_provider() -> None:
    assert isinstance(build_provider("mock"), MockProvider)
    assert isinstance(build_provider("claude"), ClaudeProvider)
    assert isinstance(build_provider("openai"), OpenAIProvider)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        build_provider("gemini")


def test_default_provider_is_mock() -> None:
    # settings.LLM_PROVIDER defaults to "mock" so the app runs credential-free.
    assert isinstance(get_llm_provider(), MockProvider)


def test_openai_without_key_resolves_to_claude_when_anthropic_key_exists(monkeypatch) -> None:
    """Asking for a real model with only the other real model's key configured
    should use the model that exists, not fail on the one that does not."""
    from app.core.config import settings
    from app.llm.factory import resolve_provider_name

    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    assert resolve_provider_name("openai") == "claude"


def test_openai_without_any_key_stays_openai(monkeypatch) -> None:
    """With neither key set there is nothing to substitute — the lazy
    call-time failure with its clear message must stand unchanged."""
    from app.core.config import settings
    from app.llm.factory import resolve_provider_name

    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    assert resolve_provider_name("openai") == "openai"


def test_openai_with_its_own_key_is_never_substituted(monkeypatch) -> None:
    from app.core.config import settings
    from app.llm.factory import resolve_provider_name

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    assert resolve_provider_name("openai") == "openai"
    assert resolve_provider_name("claude") == "claude"
    assert resolve_provider_name("mock") == "mock"


def test_providers_conform_to_interface() -> None:
    for provider in (MockProvider(), ClaudeProvider(), OpenAIProvider()):
        assert isinstance(provider, LLMProvider)
        assert provider.model


# --- mock heuristic extraction ---------------------------------------------
async def test_mock_extracts_the_example_message() -> None:
    provider = MockProvider()
    completion = await provider.complete(
        system="s", user=EXAMPLE, json_schema=extraction_json_schema()
    )
    extraction = ProfileExtraction.model_validate_json(completion.text)
    assert extraction.experience_level.value == "intermediate"
    assert extraction.target_role == "computer vision engineer"
    assert extraction.weekly_hours == 10
    names = {s.name for s in extraction.skills}
    assert {"python", "computer vision"} <= names


async def test_mock_returns_seeded_responses_in_order() -> None:
    provider = MockProvider(responses=['{"goal": "first"}', "not json"])
    first = await provider.complete(system="s", user="x")
    second = await provider.complete(system="s", user="x")
    assert first.text == '{"goal": "first"}'
    assert second.text == "not json"


# --- ProfileExtraction schema robustness -----------------------------------
def test_extraction_ignores_extra_keys() -> None:
    # A chatty model that adds keys outside the schema must not break validation.
    payload = {"goal": "become an ML engineer", "made_up_field": 123, "weekly_hours": 8}
    extraction = ProfileExtraction.model_validate(payload)
    assert extraction.goal == "become an ML engineer"
    assert extraction.weekly_hours == 8


def test_extraction_all_fields_optional() -> None:
    extraction = ProfileExtraction.model_validate({})
    assert extraction.goal is None
    assert extraction.skills == []
    assert extraction.interests == []


def test_extraction_rejects_out_of_range_hours() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProfileExtraction.model_validate({"weekly_hours": 999})


def test_extraction_json_schema_is_stable() -> None:
    schema = extraction_json_schema()
    assert schema["type"] == "object"
    assert "skills" in schema["properties"]
    assert "weekly_hours" in schema["properties"]

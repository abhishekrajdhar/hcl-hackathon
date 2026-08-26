"""Unit tests for career discovery and goal intelligence (no DB, no model)."""

from __future__ import annotations

import pytest

from app.engines.chat.intent import IntentKind, classify_goal_type, detect_intent
from app.engines.discovery import ROLES, suggest_careers


# --- career discovery --------------------------------------------------------
def test_interest_match_outranks_a_generic_springboard() -> None:
    out = suggest_careers(["language", "chatbots"], {"python": 0.8})
    assert out[0].role.slug == "nlp-engineer"
    assert any("language" in r for r in out[0].reasons)


def test_existing_skills_surface_as_springboards() -> None:
    out = suggest_careers([], {"sql": 0.8, "docker-containers": 0.6}, top_k=7)
    ranked = {s.role.slug: s.score for s in out}
    assert ranked["data-engineer"] > 0
    assert ranked["mlops-engineer"] > 0


def test_no_signals_returns_a_browsable_menu_not_an_error() -> None:
    out = suggest_careers([], {})
    assert len(out) == 3
    assert all(s.score == 0.0 for s in out)
    # stable catalogue order, not an arbitrary shuffle
    assert [s.role.slug for s in out] == [r.slug for r in ROLES[:3]]


def test_deterministic_for_identical_signals() -> None:
    a = suggest_careers(["vision"], {"python": 0.5})
    b = suggest_careers(["vision"], {"python": 0.5})
    assert [(s.role.slug, s.score) for s in a] == [(s.role.slug, s.score) for s in b]


def test_every_role_targets_only_graph_skills() -> None:
    from app.db.seeds.skill_graph import SKILLS

    slugs = {s.slug for s in SKILLS}
    for role in ROLES:
        for slug, level in role.target_skills:
            assert slug in slugs, f"{role.slug} targets unknown skill {slug}"
            assert 0 < level <= 1
        for slug in role.springboards:
            assert slug in slugs, f"{role.slug} springboard {slug} unknown"


def test_reasons_carry_evidence() -> None:
    out = suggest_careers(["images and cameras"], {"deep-learning": 0.6})
    top = out[0]
    assert top.role.slug == "computer-vision-engineer"
    assert top.reasons, "a scored suggestion must explain itself"


# --- goal intelligence -------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "kind", "goal_type"),
    [
        ("I don't know what I want to do", IntentKind.CAREER_DISCOVERY, None),
        ("not sure which path fits me, help me decide", IntentKind.CAREER_DISCOVERY, None),
        ("I want to become an ML engineer", IntentKind.SET_GOAL, "career"),
        ("I want to learn deep learning", IntentKind.SET_GOAL, "skill"),
        ("I want an internship in data science", IntentKind.SET_GOAL, "internship"),
        ("I want to switch from web development to machine learning", IntentKind.SET_GOAL, "transition"),
        ("what should I learn next?", IntentKind.NEXT_ACTION, None),
    ],
)
def test_goal_intelligence_routing(text: str, kind: IntentKind, goal_type: str | None) -> None:
    intent = detect_intent(text)
    assert intent.kind is kind
    assert intent.goal_type == goal_type


def test_uncertainty_beats_a_spurious_goal_match() -> None:
    # contains goal-ish words, but the learner is asking for direction
    intent = detect_intent("I don't know what career I want, maybe help me choose?")
    assert intent.kind is IntentKind.CAREER_DISCOVERY
    assert intent.goal_text is None


def test_classify_goal_type_without_a_goal_is_none() -> None:
    assert classify_goal_type("show me my roadmap", None) is None

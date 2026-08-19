"""Unit tests for deterministic intent detection (no DB, no model)."""

from __future__ import annotations

from app.engines.chat import IntentKind, detect_intent


def test_set_goal() -> None:
    i = detect_intent("I want to become a computer vision engineer.")
    assert i.kind == IntentKind.SET_GOAL
    assert i.goal_text == "computer vision engineer"


def test_next_action() -> None:
    assert detect_intent("What should I learn next?").kind == IntentKind.NEXT_ACTION
    assert detect_intent("what's next?").kind == IntentKind.NEXT_ACTION


def test_explain_recommendation() -> None:
    i = detect_intent("Why are you recommending PyTorch?")
    assert i.kind == IntentKind.EXPLAIN_RECOMMENDATION
    assert i.resource_ref and "pytorch" in i.resource_ref.lower()


def test_can_i_skip() -> None:
    i = detect_intent("Can I skip statistics?")
    assert i.kind == IntentKind.CAN_I_SKIP
    assert i.skill_ref == "statistics"


def test_report_completion() -> None:
    i = detect_intent("I completed the CNN course.")
    assert i.kind == IntentKind.REPORT_COMPLETION
    assert i.resource_ref and "cnn" in i.resource_ref.lower()


def test_report_score() -> None:
    i = detect_intent("I scored 92% on the assessment.")
    assert i.kind == IntentKind.REPORT_SCORE
    assert abs(i.score - 0.92) < 1e-9


def test_weekly_plan() -> None:
    assert detect_intent("What should I do this week?").kind == IntentKind.WEEKLY_PLAN


def test_search() -> None:
    i = detect_intent("find courses on transformers")
    assert i.kind == IntentKind.SEARCH_RESOURCES
    assert i.query == "transformers"


def test_show_intents() -> None:
    assert detect_intent("show me my roadmap").kind == IntentKind.SHOW_PATH
    assert detect_intent("how am I doing?").kind == IntentKind.SHOW_PROGRESS
    assert detect_intent("what are my skill gaps?").kind == IntentKind.SHOW_GAPS


def test_greeting_and_unknown() -> None:
    assert detect_intent("hi there").kind == IntentKind.GREETING
    assert detect_intent("the weather is nice").kind == IntentKind.UNKNOWN


def test_detection_is_deterministic() -> None:
    msg = "Why are you recommending PyTorch?"
    kinds = {detect_intent(msg).kind for _ in range(50)}
    assert len(kinds) == 1

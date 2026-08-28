"""Unit tests for deterministic intent detection (no DB, no model)."""

from __future__ import annotations

import pytest

from app.engines.chat import IntentKind, detect_intent
from app.engines.chat.intent import extract_known_skills, extract_weekly_hours


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


# --- spoken extras: time budget and skill claims ----------------------------
# These ride on any intent, because a learner states a goal, a budget and their
# existing skills in one breath — especially when speaking rather than typing.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I only have about an hour a day", 7),
        ("roughly 2 hours a day", 14),
        ("I can do 10 hours a week", 10),
        ("maybe half an hour a day", 4),
        ("a couple of hours a week", 2),
        ("three hours every evening", 21),
        ("I have no idea how much time", None),
        ("I want to become an ML engineer", None),
    ],
)
def test_extract_weekly_hours(text: str, expected: int | None) -> None:
    assert extract_weekly_hours(text) == expected


def test_weekly_hours_is_clamped() -> None:
    assert extract_weekly_hours("50 hours a day") == 168


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I'm already comfortable with Python", ["python"]),
        ("I already know SQL and pandas", ["sql", "pandas"]),
        ("I am confident with linear algebra and statistics", ["linear algebra", "statistics"]),
        ("I am familiar with git", ["git"]),
        ("I am comfortable with natural language processing", ["natural language processing"]),
        # not skill claims
        ("I want to learn Python", []),
        ("I know that this is hard", []),
        ("I know it is difficult", []),
    ],
)
def test_extract_known_skills(text: str, expected: list[str]) -> None:
    assert extract_known_skills(text) == expected


def test_extras_ride_along_with_the_intent() -> None:
    intent = detect_intent(
        "I want to become a machine learning engineer, but I only have about an "
        "hour a day and I'm already comfortable with Python."
    )
    assert intent.kind is IntentKind.SET_GOAL
    assert intent.goal_text == "machine learning engineer"
    assert intent.weekly_hours == 7
    assert intent.known_skills == ["python"]


def test_extras_are_absent_when_unstated() -> None:
    intent = detect_intent("what should I learn next?")
    assert intent.weekly_hours is None
    assert intent.known_skills == []


# --- subject-matter questions ------------------------------------------------
# Previously every message starting with "why" was answered as if it were about
# a recommendation, and open questions fell to a capability menu.


@pytest.mark.parametrize(
    ("text", "skill", "related"),
    [
        ("Why is linear algebra important for machine learning?", "linear algebra", "machine learning"),
        ("Do I really need calculus for deep learning?", "calculus", "deep learning"),
        ("How does statistics relate to machine learning?", "statistics", "machine learning"),
        # skill_ref keeps the learner's own capitalisation; the resolver is
        # case-insensitive, so nothing downstream cares.
        ("Why do I need SQL for machine learning?", "SQL", "machine learning"),
    ],
)
def test_prerequisite_questions_route_to_the_graph(
    text: str, skill: str, related: str
) -> None:
    intent = detect_intent(text)
    assert intent.kind is IntentKind.EXPLAIN_PREREQUISITE
    assert intent.skill_ref == skill
    assert intent.related_skill_ref == related


@pytest.mark.parametrize(
    "text",
    [
        "What is the difference between CNNs and transformers?",
        "Should I learn PyTorch or TensorFlow?",
        "Explain gradient descent",
        "What are embeddings?",
    ],
)
def test_open_subject_questions_are_recognised(text: str) -> None:
    assert detect_intent(text).kind is IntentKind.GENERAL_QUESTION


def test_recommendation_why_still_routes_to_recommendations() -> None:
    intent = detect_intent("Why are you recommending PyTorch?")
    assert intent.kind is IntentKind.EXPLAIN_RECOMMENDATION


def test_asking_about_completed_milestones_is_a_progress_query() -> None:
    """"What milestones have I completed" asks ABOUT progress; it must not be
    swallowed by the completion-report pattern ("i completed ...") or fall to
    the general-question branch, whose model cannot see learner data."""
    for msg in (
        "what milestones do I have completed",
        "which milestones have I achieved?",
        "what have I finished so far",
        "how many courses did I complete",
        "show my milestones",
    ):
        assert detect_intent(msg).kind == IntentKind.SHOW_PROGRESS, msg


def test_reporting_a_completion_still_reports() -> None:
    assert detect_intent("I completed the Docker course").kind == IntentKind.REPORT_COMPLETION
    assert detect_intent("I just finished Learn Python").kind == IntentKind.REPORT_COMPLETION


def test_bare_affirmation_gets_standing_not_greeting() -> None:
    """A "yes" after an offer must answer with something, not loop back to
    the capabilities greeting."""
    for msg in ("yes", "Yes you can see", "sure", "go ahead", "ok!", "yes please"):
        assert detect_intent(msg).kind == IntentKind.AFFIRMATION, msg
    # A sentence that merely starts with yes is not a bare go-ahead.
    assert detect_intent("yes I want to become a data analyst").kind == IntentKind.SET_GOAL

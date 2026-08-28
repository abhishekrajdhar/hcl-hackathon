"""Unit tests for prior-learning suppression (no DB, no model)."""

from __future__ import annotations

import uuid

import pytest

from app.engines.recommendation import (
    CatalogueEntry,
    DeclaredCourse,
    build_suppressions,
    match_declared_courses,
)

A = uuid.uuid4()
_RID1 = uuid.uuid4()
_RID2 = uuid.uuid4()
B = uuid.uuid4()
C = uuid.uuid4()

CATALOGUE = [
    CatalogueEntry(A, "Deep Learning (Goodfellow et al.)", "MIT Press", "https://www.deeplearningbook.org/"),
    CatalogueEntry(B, "Machine Learning Specialization", "Coursera", "https://coursera.org/ml"),
    CatalogueEntry(C, "Deep Learning", "Fast.ai", None),
]


def test_matches_on_explicit_resource_id() -> None:
    assert match_declared_courses([DeclaredCourse("anything", resource_id=B)], CATALOGUE) == {
        B: "anything"
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://www.deeplearningbook.org/",
        "http://deeplearningbook.org",
        "deeplearningbook.org/?utm_source=x",
    ],
)
def test_matches_on_url_regardless_of_scheme_www_slash_or_query(url: str) -> None:
    assert match_declared_courses([DeclaredCourse("t", url=url)], CATALOGUE) == {A: "t"}


def test_matches_on_normalised_title() -> None:
    assert match_declared_courses(
        [DeclaredCourse("machine   learning specialization!")], CATALOGUE
    ) == {B: "machine   learning specialization!"}


def test_disagreeing_provider_vetoes_a_title_match() -> None:
    assert match_declared_courses([DeclaredCourse("Deep Learning", provider="Udemy")], CATALOGUE) == {}


def test_agreeing_provider_keeps_a_title_match() -> None:
    assert match_declared_courses([DeclaredCourse("Deep Learning", provider="fast.ai")], CATALOGUE) == {
        C: "Deep Learning"
    }


def test_does_not_fuzzy_match() -> None:
    # Hiding a resource the learner never took is worse than showing one they did.
    assert match_declared_courses([DeclaredCourse("Deep Learning with PyTorch")], CATALOGUE) == {}


def test_unknown_course_matches_nothing() -> None:
    assert match_declared_courses([DeclaredCourse("Underwater Basket Weaving")], CATALOGUE) == {}


def test_recorded_completion_outranks_a_declaration() -> None:
    merged = build_suppressions([A], {A: "declared", B: "declared"})
    assert merged[A] == "completed_here"
    assert merged[B] == "declared_completed"


def test_no_history_suppresses_nothing() -> None:
    assert build_suppressions([], {}) == {}


# --- guarded fuzzy tier ------------------------------------------------------
def test_fuzzy_matches_a_shorthand_declaration() -> None:
    """"CS50 Python" is how a human declares the Harvard course; every identity
    token appears in exactly one catalogue title, so it matches."""
    catalogue = [
        CatalogueEntry(resource_id=_RID1, title="Harvard CS50's Artificial Intelligence with Python - Full University Course"),
        CatalogueEntry(resource_id=_RID2, title="Docker Tutorial for Beginners"),
    ]
    matched = match_declared_courses([DeclaredCourse(title="CS50 python")], catalogue)
    assert matched == {_RID1: "CS50 python"}


def test_fuzzy_refuses_when_two_candidates_qualify() -> None:
    """Ambiguity means no suppression — showing a duplicate beats hiding a
    course the learner never took."""
    catalogue = [
        CatalogueEntry(resource_id=_RID1, title="Python Full Course for Beginners"),
        CatalogueEntry(resource_id=_RID2, title="Python Full Course 2025 Edition"),
    ]
    assert match_declared_courses([DeclaredCourse(title="python full")], catalogue) == {}


def test_fuzzy_needs_two_meaningful_tokens() -> None:
    """A single word like "python" would match half the catalogue."""
    catalogue = [CatalogueEntry(resource_id=_RID1, title="Python for Everybody")]
    assert match_declared_courses([DeclaredCourse(title="Python course")], catalogue) == {}


def test_fuzzy_respects_provider_disagreement() -> None:
    catalogue = [
        CatalogueEntry(resource_id=_RID1, title="Deep Learning Specialization Overview", provider="DeepLearning.AI"),
    ]
    matched = match_declared_courses(
        [DeclaredCourse(title="deep learning specialization", provider="Coursera Plus")], catalogue
    )
    assert matched == {}

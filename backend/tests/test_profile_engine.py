"""Unit tests for the pure profile engines: proficiency math and validation.

No database — these exercise the deterministic core directly.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.engines.profile import (
    ProfileSnapshot,
    assessment_skill_scores,
    blend_proficiency,
    clamp01,
    evidence_strength,
    level_to_proficiency,
    observation_weight,
    proficiency_to_level,
    validate_profile,
)
from app.engines.profile.proficiency import DEFAULT_MAX_DELTA
from app.models.enums import EvidenceSource


# --- normalization ---------------------------------------------------------
def test_proficiency_level_round_trip() -> None:
    assert proficiency_to_level(0.85, 5) == 4.25
    assert level_to_proficiency(4.25, 5) == 0.85
    assert proficiency_to_level(0.0, 5) == 0.0
    assert proficiency_to_level(1.0, 10) == 10.0


def test_normalization_clamps_out_of_range() -> None:
    assert proficiency_to_level(1.5, 5) == 5.0
    assert proficiency_to_level(-0.5, 5) == 0.0
    assert level_to_proficiency(20, 5) == 1.0
    assert level_to_proficiency(5, 0) == 0.0  # guard against zero scale


def test_clamp01() -> None:
    assert clamp01(-1) == 0.0
    assert clamp01(2) == 1.0
    assert clamp01(0.42) == 0.42


# --- evidence weighting ----------------------------------------------------
def test_evidence_strength_scales_with_question_count() -> None:
    assert evidence_strength(0) == 0.0
    assert evidence_strength(4) == 0.5
    assert evidence_strength(8) == 1.0
    assert evidence_strength(50) == 1.0  # capped


def test_assessment_outweighs_completion_outweighs_inference() -> None:
    a = observation_weight(EvidenceSource.ASSESSMENT)
    c = observation_weight(EvidenceSource.COMPLETION)
    i = observation_weight(EvidenceSource.INFERRED)
    assert a > c > i


# --- blend -----------------------------------------------------------------
def test_blend_moves_toward_observation() -> None:
    up = blend_proficiency(0.6, 0.9, weight=0.5)
    assert 0.6 < up.new_proficiency < 0.9
    assert up.delta > 0

    down = blend_proficiency(0.6, 0.2, weight=0.5)
    assert 0.2 < down.new_proficiency < 0.6
    assert down.delta < 0


def test_blend_weight_zero_is_noop() -> None:
    up = blend_proficiency(0.42, 0.99, weight=0.0)
    assert up.new_proficiency == 0.42
    assert up.delta == 0.0


def test_blend_is_bounded_per_event() -> None:
    up = blend_proficiency(0.0, 1.0, weight=1.0)
    assert up.new_proficiency == pytest.approx(DEFAULT_MAX_DELTA)


def test_blend_stays_in_unit_interval() -> None:
    up = blend_proficiency(0.95, 1.0, weight=1.0, max_delta=1.0)
    assert up.new_proficiency <= 1.0
    down = blend_proficiency(0.05, 0.0, weight=1.0, max_delta=1.0)
    assert down.new_proficiency >= 0.0


def test_blend_confidence_only_rises() -> None:
    up = blend_proficiency(0.5, 0.5, weight=0.8, prior_confidence=0.3)
    assert up.new_confidence > 0.3


def test_blend_is_deterministic() -> None:
    args = dict(weight=0.6, prior_confidence=0.4)
    results = {blend_proficiency(0.3, 0.7, **args).new_proficiency for _ in range(50)}
    assert len(results) == 1


# --- per-skill scoring from an attempt -------------------------------------
def test_assessment_skill_scores_groups_by_skill() -> None:
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    responses = [
        {"skill_id": str(s1), "is_correct": True, "points_awarded": 1.0, "points_possible": 1.0},
        {"skill_id": str(s1), "is_correct": False, "points_awarded": 0.0, "points_possible": 1.0},
        {"skill_id": str(s2), "is_correct": True, "points_awarded": 2.0, "points_possible": 2.0},
    ]
    scores = {s.skill_id: s for s in assessment_skill_scores(responses)}
    assert scores[s1].ratio == 0.5
    assert scores[s2].ratio == 1.0
    assert scores[s1].total == 2


def test_assessment_skill_scores_uses_fallback_skill() -> None:
    fallback = uuid.uuid4()
    responses = [{"is_correct": True, "points_awarded": 1.0, "points_possible": 1.0}]
    scores = assessment_skill_scores(responses, fallback_skill_id=fallback)
    assert len(scores) == 1
    assert scores[0].skill_id == fallback


def test_assessment_skill_scores_ratio_falls_back_to_counts() -> None:
    skill = uuid.uuid4()
    # points_possible absent → fall back to correct/total.
    responses = [
        {"skill_id": str(skill), "is_correct": True, "points_awarded": 0.0},
        {"skill_id": str(skill), "is_correct": False, "points_awarded": 0.0},
    ]
    scores = assessment_skill_scores(responses)
    assert scores[0].ratio == 0.5


def test_assessment_skill_scores_is_deterministically_ordered() -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    responses = [
        {"skill_id": str(i), "is_correct": True, "points_awarded": 1.0, "points_possible": 1.0}
        for i in ids
    ]
    order1 = [s.skill_id for s in assessment_skill_scores(responses)]
    order2 = [s.skill_id for s in assessment_skill_scores(list(reversed(responses)))]
    assert order1 == order2 == sorted(ids, key=str)


# --- realistic scenario ----------------------------------------------------
def test_strong_pass_raises_and_weak_pass_barely_moves() -> None:
    # A 10-question assessment (full strength).
    strong_weight = observation_weight(EvidenceSource.ASSESSMENT, strength=evidence_strength(10))
    high = blend_proficiency(0.4, 0.95, weight=strong_weight)

    # A single-question quiz (weak evidence).
    weak_weight = observation_weight(EvidenceSource.ASSESSMENT, strength=evidence_strength(1))
    low = blend_proficiency(0.4, 0.95, weight=weak_weight)

    assert high.delta > low.delta > 0


# --- validation ------------------------------------------------------------
TODAY = date(2026, 8, 18)


def _snap(**kw: object) -> ProfileSnapshot:
    base = dict(weekly_hours=5, experience_level="beginner")
    base.update(kw)
    return ProfileSnapshot(**base)  # type: ignore[arg-type]


def test_valid_profile_has_no_errors() -> None:
    result = validate_profile(
        _snap(
            weekly_hours=8,
            goal_text_raw="Become an ML engineer",
            skill_count=3,
            max_proficiency=0.6,
            proficiencies=(0.6, 0.4, 0.2),
            target_deadline=date(2026, 12, 1),
        ),
        today=TODAY,
    )
    assert result.is_valid
    assert not result.errors


def test_past_deadline_is_error() -> None:
    result = validate_profile(_snap(target_deadline=date(2025, 1, 1)), today=TODAY)
    assert not result.is_valid
    assert any(e.code == "deadline_in_past" for e in result.errors)


def test_out_of_range_proficiency_is_error() -> None:
    result = validate_profile(_snap(proficiencies=(0.5, 1.7), skill_count=2), today=TODAY)
    assert not result.is_valid
    assert any(e.code == "proficiency_out_of_range" for e in result.errors)


def test_zero_hours_is_warning_not_error() -> None:
    result = validate_profile(_snap(weekly_hours=0, goal_text_raw="x", skill_count=1), today=TODAY)
    assert result.is_valid  # warning does not invalidate
    assert any(w.code == "weekly_hours_too_low" for w in result.warnings)


def test_missing_goal_and_role_warns() -> None:
    result = validate_profile(_snap(skill_count=1), today=TODAY)
    assert any(w.code == "no_goal_or_role" for w in result.warnings)


def test_expert_without_skills_warns() -> None:
    result = validate_profile(
        _snap(experience_level="expert", skill_count=3, max_proficiency=0.2, goal_text_raw="x"),
        today=TODAY,
    )
    assert any(w.code == "experience_skill_mismatch" for w in result.warnings)


def test_no_skills_warns() -> None:
    result = validate_profile(_snap(goal_text_raw="x", skill_count=0), today=TODAY)
    assert any(w.code == "no_skills" for w in result.warnings)

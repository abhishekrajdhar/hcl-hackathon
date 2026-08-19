"""Unit tests for the pure adaptive engine: the MVP formula and decisions."""

from __future__ import annotations

import pytest

from app.engines.adaptive import (
    decide,
    level_band,
    recover_previous,
    update_from_assessment,
    update_from_completion,
)


# --- SkillProficiencyUpdater (0.6*old + 0.4*score) -------------------------
def test_mvp_formula() -> None:
    assert update_from_assessment(0.3, 1.0) == pytest.approx(0.58)   # 0.6*0.3 + 0.4*1.0
    assert update_from_assessment(0.5, 0.9) == pytest.approx(0.66)
    assert update_from_assessment(0.0, 0.0) == 0.0
    assert update_from_assessment(0.85, 1.0) == pytest.approx(0.91)


def test_formula_is_clamped() -> None:
    assert update_from_assessment(1.0, 1.0) == 1.0
    assert update_from_assessment(2.0, 2.0) == 1.0  # inputs clamped first
    assert update_from_assessment(-1.0, -1.0) == 0.0


def test_recover_previous_inverts_exactly() -> None:
    for old, score in [(0.3, 1.0), (0.5, 0.9), (0.85, 1.0), (0.2, 0.4)]:
        new = update_from_assessment(old, score)
        assert recover_previous(new, score) == pytest.approx(old, abs=1e-4)


def test_completion_update_only_raises_toward_taught_level() -> None:
    assert update_from_completion(0.4, 0.8) > 0.4          # nudged up
    assert update_from_completion(0.4, 0.8) <= 0.8         # not past what it teaches
    assert update_from_completion(0.9, 0.5) == 0.9         # never lowers


def test_formula_is_deterministic() -> None:
    assert len({update_from_assessment(0.42, 0.73) for _ in range(50)}) == 1


# --- adaptive decisions (spec thresholds) ----------------------------------
def test_level_bands() -> None:
    assert level_band(0.85) == "advanced"        # > 0.80
    assert level_band(0.70) == "intermediate"    # 0.60..0.80
    assert level_band(0.55) == "foundational"    # 0.50..0.60
    assert level_band(0.40) == "remedial"        # < 0.50


def test_skill_above_080_skips_introductory() -> None:
    assert decide(0.85).skip_introductory is True
    assert decide(0.80).skip_introductory is False  # strictly greater


def test_skill_between_060_and_080_continues_intermediate() -> None:
    d = decide(0.70)
    assert d.continue_intermediate is True
    assert d.skip_introductory is False
    assert d.recommend_remedial is False


def test_skill_below_050_recommends_remedial() -> None:
    assert decide(0.40).recommend_remedial is True
    assert decide(0.50).recommend_remedial is False


def test_score_below_050_inserts_remediation() -> None:
    assert decide(0.5, assessment_score=0.4).insert_remediation is True
    assert decide(0.5, assessment_score=0.5).insert_remediation is False


def test_score_above_085_unlocks_next_milestone() -> None:
    assert decide(0.5, assessment_score=0.9).unlock_next_milestone is True
    assert decide(0.5, assessment_score=0.85).unlock_next_milestone is False


def test_decision_without_score_has_no_score_triggers() -> None:
    d = decide(0.9)  # no assessment score
    assert d.insert_remediation is False
    assert d.unlock_next_milestone is False
    assert d.skip_introductory is True  # level-based still applies

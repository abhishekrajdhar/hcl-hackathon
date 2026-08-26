"""Unit tests for career-readiness scoring (no DB, no model)."""

from __future__ import annotations

from app.engines.readiness import TargetSkill, compute_readiness


def _t(name: str, required: float, current: float) -> TargetSkill:
    return TargetSkill(skill_id=name, name=name, required_level=required, current_level=current)


def test_overall_is_weighted_over_evidenced_dimensions_only() -> None:
    r = compute_readiness([_t("dsa", 0.8, 0.8)], [], 0, 0, "unknown")
    # only knowledge has evidence; overall must equal it, not be dragged to 0
    assert r.overall == 1.0
    assert {d.key: d.score for d in r.dimensions}["assessments"] is None


def test_no_evidence_at_all_is_zero_not_a_crash() -> None:
    r = compute_readiness([], [], 0, 0, "unknown")
    assert r.overall == 0.0
    assert r.weakest is None


def test_readiness_is_capped_at_the_requirement() -> None:
    r = compute_readiness([_t("python", 0.8, 0.95)], [], 0, 0, "unknown")
    assert r.skills[0].readiness == 1.0, "overshooting a target is met, not >100%"


def test_weakest_dimension_is_named() -> None:
    r = compute_readiness([_t("a", 0.8, 0.72)], [0.95], 0, 2, "on_track")
    assert r.weakest == "projects"


def test_skills_are_sorted_worst_first() -> None:
    r = compute_readiness([_t("strong", 0.8, 0.8), _t("weak", 0.8, 0.2)], [], 0, 0, "unknown")
    assert r.skills[0].name == "weak"


def test_slower_pace_drags_momentum_not_everything() -> None:
    on = compute_readiness([_t("a", 0.8, 0.8)], [0.9], 1, 1, "on_track")
    slow = compute_readiness([_t("a", 0.8, 0.8)], [0.9], 1, 1, "slower")
    assert slow.overall < on.overall
    assert {d.key: d.score for d in slow.dimensions}["knowledge"] == 1.0

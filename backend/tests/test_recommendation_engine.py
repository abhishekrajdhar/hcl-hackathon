"""Unit tests for the pure hybrid recommendation scorer. No DB, no model."""

from __future__ import annotations

import uuid

from app.engines.recommendation import (
    CandidateResource,
    LearnerContext,
    RecommendationWeights,
    ResourcePrerequisite,
    ScoringConfig,
    TaughtSkill,
    score_resource,
    top_factors,
)
from app.engines.recommendation.scoring import (
    difficulty_match,
    prerequisite_readiness,
    quality_signal,
    skill_gap_match,
    time_fit,
)

ML = uuid.uuid5(uuid.NAMESPACE_DNS, "ml")
DL = uuid.uuid5(uuid.NAMESPACE_DNS, "dl")
OTHER = uuid.uuid5(uuid.NAMESPACE_DNS, "other")


def _learner(**kw) -> LearnerContext:
    base = dict(proficiencies={ML: 0.2}, gaps={ML: 0.6, DL: 0.7})
    base.update(kw)
    return LearnerContext(**base)


# --- individual signals ----------------------------------------------------
def test_gap_match_counts_only_advancing_gap_skills() -> None:
    taught = [TaughtSkill(ML, 0.0, 0.7), TaughtSkill(OTHER, 0.0, 0.5)]
    match, matched = skill_gap_match(taught, {ML: 0.6, DL: 0.7}, {ML: 0.2})
    assert ML in matched and OTHER not in matched  # OTHER is not a gap
    assert match > 0


def test_gap_match_ignores_already_surpassed_band() -> None:
    # resource only teaches up to 0.3 but learner already at 0.5 -> no advance
    match, matched = skill_gap_match([TaughtSkill(ML, 0.0, 0.3)], {ML: 0.6}, {ML: 0.5})
    assert match == 0.0 and matched == []


def test_prerequisite_readiness_gate() -> None:
    r, unmet = prerequisite_readiness([ResourcePrerequisite(ML, 0.5)], {ML: 0.2})
    assert r == 0.0 and unmet == [ML]
    r2, unmet2 = prerequisite_readiness([ResourcePrerequisite(ML, 0.5)], {ML: 0.8})
    assert r2 == 1.0 and unmet2 == []
    assert prerequisite_readiness([], {})[0] == 1.0  # no prereqs -> ready


def test_difficulty_penalises_too_advanced_more_than_too_easy() -> None:
    cfg = ScoringConfig()
    too_advanced = difficulty_match([TaughtSkill(ML, 0.8, 1.0)], {ML: 0.2}, cfg)
    too_easy = difficulty_match([TaughtSkill(ML, 0.0, 0.4)], {ML: 0.6}, cfg)
    good = difficulty_match([TaughtSkill(ML, 0.2, 0.7)], {ML: 0.2}, cfg)
    assert good > too_easy > too_advanced


def test_quality_prefers_explicit_score_then_rating() -> None:
    assert quality_signal(0.9, 4.0) == 0.9
    assert quality_signal(None, 5.0) == 1.0
    assert quality_signal(None, None) == 0.5


def test_time_fit_decays_for_very_long_resources() -> None:
    cfg = ScoringConfig()
    assert time_fit(10, 10, cfg) == 1.0          # ~1 week
    assert time_fit(200, 5, cfg) < 1.0           # 40 weeks -> penalised


# --- combined score & the stage-appropriateness guarantee ------------------
def _dl_course() -> CandidateResource:
    return CandidateResource(
        resource_id=uuid.uuid4(), semantic_similarity=0.95,
        taught=(TaughtSkill(DL, 0.4, 0.8),),
        prerequisites=(ResourcePrerequisite(ML, 0.5),),  # learner has ML=0.2 -> unmet
        difficulty=5, modality="video", quality_score=0.95, rating=4.9,
    )


def _ml_course() -> CandidateResource:
    return CandidateResource(
        resource_id=uuid.uuid4(), semantic_similarity=0.70,
        taught=(TaughtSkill(ML, 0.0, 0.7),),
        prerequisites=(),
        difficulty=3, modality="video", quality_score=0.90, rating=4.8,
    )


def test_advanced_resource_with_unmet_prereqs_is_flagged_unready() -> None:
    scored = score_resource(_dl_course(), _learner())
    assert scored.is_ready is False
    assert scored.features["prerequisite_match"] == 0.0
    assert ML in scored.unmet_prerequisite_ids


def test_ready_foundational_beats_unready_advanced_despite_similarity() -> None:
    learner = _learner()
    dl = score_resource(_dl_course(), learner)   # similarity 0.95 but unready
    ml = score_resource(_ml_course(), learner)   # similarity 0.70 but ready
    assert ml.is_ready and not dl.is_ready
    # ready-first ordering puts the learnable course ahead
    ordered = sorted([dl, ml], key=lambda s: (s.is_ready, s.score), reverse=True)
    assert ordered[0].resource_id == ml.resource_id


def test_popularity_alone_does_not_win() -> None:
    learner = _learner()
    ml = score_resource(_ml_course(), learner)
    # a 5-star, high-quality but OFF-TOPIC resource (no gap overlap, low similarity)
    offtopic = CandidateResource(
        resource_id=uuid.uuid4(), semantic_similarity=0.1,
        taught=(TaughtSkill(OTHER, 0.0, 0.5),), quality_score=1.0, rating=5.0, modality="text",
    )
    assert score_resource(offtopic, learner).score < ml.score


def test_score_is_normalised_to_unit_interval() -> None:
    learner = _learner()
    for cand in (_dl_course(), _ml_course()):
        s = score_resource(cand, learner)
        assert 0.0 <= s.score <= 1.0
        for value in s.features.values():
            assert 0.0 <= value <= 1.0


def test_default_weights_match_specified_formula() -> None:
    w = RecommendationWeights()
    assert (w.semantic_similarity, w.skill_gap_match, w.prerequisite_match) == (0.30, 0.25, 0.20)
    assert (w.difficulty_match, w.preference_match, w.quality_score, w.historical_success) == (
        0.10, 0.05, 0.05, 0.05,
    )
    assert abs(w.total() - 1.0) < 1e-9  # default (time_fit 0) sums to 1


def test_custom_weights_change_ranking() -> None:
    learner = _learner()
    cand = _ml_course()
    only_quality = score_resource(
        cand, learner,
        weights=RecommendationWeights(
            semantic_similarity=0, skill_gap_match=0, prerequisite_match=0, difficulty_match=0,
            preference_match=0, quality_score=1.0, historical_success=0,
        ),
    )
    assert abs(only_quality.score - only_quality.features["quality_score"]) < 1e-6


def test_scoring_is_deterministic() -> None:
    learner = _learner()
    cand = _ml_course()
    scores = {score_resource(cand, learner).score for _ in range(50)}
    assert len(scores) == 1


def test_top_factors_are_ordered_by_contribution() -> None:
    scored = score_resource(_ml_course(), _learner())
    factors = top_factors(scored, limit=3)
    values = [v for _, v in factors]
    assert values == sorted(values, reverse=True)
    assert len(factors) <= 3

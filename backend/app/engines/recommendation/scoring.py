"""Deterministic hybrid ranking for learning-resource recommendations.

Combines several 0-1 signals into one configurable weighted score, normalised
so the result is always in [0, 1]. Pure — no DB, no model, no clock — so a
ranking is reproducible and every number is auditable.

Two ideas keep recommendations appropriate for the learner's CURRENT stage,
rather than just returning popular or highly-similar content:

1. `prerequisite_match` is a weighted feature, AND
2. a readiness GATE marks a resource unready when the learner does not meet its
   prerequisites. The service demotes/excludes unready resources, so a
   high-similarity advanced course whose prerequisites are unmet is never
   recommended over something the learner can actually start.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RecommendationWeights:
    """Hybrid-score weights. Need not sum to 1 — the score is normalised by the
    total weight — but the defaults reproduce the specified formula exactly."""

    semantic_similarity: float = 0.30
    skill_gap_match: float = 0.25
    prerequisite_match: float = 0.20
    difficulty_match: float = 0.10
    preference_match: float = 0.05
    quality_score: float = 0.05
    historical_success: float = 0.05
    #: Fit to the weekly-hours budget. Off by default so the default ranking is
    #: exactly the given 7-term formula; computed and reported regardless.
    time_fit: float = 0.0

    def total(self) -> float:
        return (
            self.semantic_similarity
            + self.skill_gap_match
            + self.prerequisite_match
            + self.difficulty_match
            + self.preference_match
            + self.quality_score
            + self.historical_success
            + self.time_fit
        )


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    #: Penalty per unit the resource starts ABOVE the learner (too advanced).
    too_advanced_coef: float = 1.5
    #: Penalty per unit the resource ends BELOW the learner (too easy).
    too_easy_coef: float = 0.7
    #: Neutral prior when there is no learning history.
    neutral_historical: float = 0.5
    #: Ideal number of weeks a single resource should take at the weekly budget.
    ideal_weeks: float = 4.0
    #: Weekly-hours default when the learner has not stated one.
    default_weekly_hours: int = 5


@dataclass(frozen=True, slots=True)
class TaughtSkill:
    skill_id: uuid.UUID
    level_from: float = 0.0
    level_to: float = 1.0
    coverage_weight: float = 1.0


@dataclass(frozen=True, slots=True)
class ResourcePrerequisite:
    skill_id: uuid.UUID
    min_proficiency: float = 0.0


@dataclass(frozen=True, slots=True)
class CandidateResource:
    resource_id: uuid.UUID
    semantic_similarity: float          # 0-1 (1 - cosine distance, clamped)
    taught: tuple[TaughtSkill, ...] = ()
    prerequisites: tuple[ResourcePrerequisite, ...] = ()
    difficulty: int = 1
    modality: str = "mixed"
    quality_score: float | None = None
    rating: float | None = None
    estimated_hours: float = 0.0
    historical_success: float | None = None


@dataclass(frozen=True, slots=True)
class LearnerContext:
    proficiencies: Mapping[uuid.UUID, float] = field(default_factory=dict)
    gaps: Mapping[uuid.UUID, float] = field(default_factory=dict)  # skill_id -> gap (0-1)
    preferred_modalities: frozenset[str] = frozenset()
    weekly_hours: int | None = None


@dataclass(frozen=True, slots=True)
class ScoredResource:
    resource_id: uuid.UUID
    score: float
    is_ready: bool
    features: dict[str, float]
    contributions: dict[str, float]
    matched_gap_skill_ids: tuple[uuid.UUID, ...]
    unmet_prerequisite_ids: tuple[uuid.UUID, ...]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# --- individual signals ----------------------------------------------------
def skill_gap_match(
    taught: Sequence[TaughtSkill],
    gaps: Mapping[uuid.UUID, float],
    proficiencies: Mapping[uuid.UUID, float],
) -> tuple[float, list[uuid.UUID]]:
    """How much of the learner's gap this resource actually addresses.

    A taught skill counts only when it is a real gap AND the resource teaches
    above the learner's current level (so it advances them). Contributions are
    gap-size × coverage-weight, summed and capped at 1.
    """
    matched: list[uuid.UUID] = []
    total = 0.0
    for t in taught:
        gap = gaps.get(t.skill_id, 0.0)
        if gap <= 0.0:
            continue
        if t.level_to <= proficiencies.get(t.skill_id, 0.0):
            continue  # nothing new for the learner
        total += gap * t.coverage_weight
        matched.append(t.skill_id)
    return _clamp01(total), matched


def prerequisite_readiness(
    prerequisites: Sequence[ResourcePrerequisite],
    proficiencies: Mapping[uuid.UUID, float],
) -> tuple[float, list[uuid.UUID]]:
    """Fraction of prerequisites the learner meets, and which are unmet.

    No prerequisites -> fully ready. This is the current-stage guard: a resource
    with unmet prerequisites is not appropriate yet, however similar it looks.
    """
    if not prerequisites:
        return 1.0, []
    unmet = [
        p.skill_id
        for p in prerequisites
        if proficiencies.get(p.skill_id, 0.0) < p.min_proficiency
    ]
    readiness = 1.0 - (len(unmet) / len(prerequisites))
    return readiness, unmet


def difficulty_match(
    taught: Sequence[TaughtSkill],
    proficiencies: Mapping[uuid.UUID, float],
    config: ScoringConfig,
) -> float:
    """Whether the resource's level suits the learner.

    Penalises teaching that starts above the learner (too advanced, penalised
    harder) or ends below them (too easy). Averaged over the taught skills.
    """
    if not taught:
        return 0.5  # unknown -> neutral
    fits = []
    for t in taught:
        current = proficiencies.get(t.skill_id, 0.0)
        too_advanced = max(0.0, t.level_from - current)
        too_easy = max(0.0, current - t.level_to)
        penalty = config.too_advanced_coef * too_advanced + config.too_easy_coef * too_easy
        fits.append(_clamp01(1.0 - penalty))
    return sum(fits) / len(fits)


def preference_match(modality: str, preferred: frozenset[str]) -> float:
    if not preferred:
        return 0.5  # no stated preference -> neutral
    return 1.0 if modality in preferred else 0.3


def quality_signal(quality_score: float | None, rating: float | None) -> float:
    if quality_score is not None:
        return _clamp01(quality_score)
    if rating is not None:
        return _clamp01(rating / 5.0)
    return 0.5


def time_fit(estimated_hours: float, weekly_hours: int | None, config: ScoringConfig) -> float:
    """1 when a resource fits comfortably in the weekly budget; decays as it
    stretches well past the ideal number of weeks."""
    hours = max(1, weekly_hours or config.default_weekly_hours)
    if estimated_hours <= 0:
        return 0.5
    weeks = estimated_hours / hours
    if weeks <= config.ideal_weeks:
        return 1.0
    return _clamp01(1.0 - (weeks - config.ideal_weeks) / (config.ideal_weeks * 3))


# --- combined score --------------------------------------------------------
def score_resource(
    candidate: CandidateResource,
    learner: LearnerContext,
    *,
    weights: RecommendationWeights | None = None,
    config: ScoringConfig | None = None,
) -> ScoredResource:
    weights = weights or RecommendationWeights()
    config = config or ScoringConfig()

    gap_match, matched = skill_gap_match(candidate.taught, learner.gaps, learner.proficiencies)
    readiness, unmet = prerequisite_readiness(candidate.prerequisites, learner.proficiencies)
    diff = difficulty_match(candidate.taught, learner.proficiencies, config)
    pref = preference_match(candidate.modality, learner.preferred_modalities)
    quality = quality_signal(candidate.quality_score, candidate.rating)
    historical = (
        candidate.historical_success
        if candidate.historical_success is not None
        else config.neutral_historical
    )
    tfit = time_fit(candidate.estimated_hours, learner.weekly_hours, config)

    features = {
        "semantic_similarity": _clamp01(candidate.semantic_similarity),
        "skill_gap_match": gap_match,
        "prerequisite_match": readiness,
        "difficulty_match": diff,
        "preference_match": pref,
        "quality_score": quality,
        "historical_success": _clamp01(historical),
        "time_fit": tfit,
    }
    weight_map = {
        "semantic_similarity": weights.semantic_similarity,
        "skill_gap_match": weights.skill_gap_match,
        "prerequisite_match": weights.prerequisite_match,
        "difficulty_match": weights.difficulty_match,
        "preference_match": weights.preference_match,
        "quality_score": weights.quality_score,
        "historical_success": weights.historical_success,
        "time_fit": weights.time_fit,
    }
    total_weight = weights.total() or 1.0
    contributions = {k: round(weight_map[k] * features[k], 6) for k in features}
    score = round(sum(contributions.values()) / total_weight, 6)

    return ScoredResource(
        resource_id=candidate.resource_id,
        score=score,
        is_ready=not unmet,
        features={k: round(v, 6) for k, v in features.items()},
        contributions=contributions,
        matched_gap_skill_ids=tuple(matched),
        unmet_prerequisite_ids=tuple(unmet),
    )


def top_factors(scored: ScoredResource, *, limit: int = 3) -> list[tuple[str, float]]:
    """The highest-contributing factors, for explanations. Deterministic order."""
    ranked = sorted(scored.contributions.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(name, value) for name, value in ranked if value > 0][:limit]

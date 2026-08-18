"""Deterministic skill-proficiency arithmetic.

Proficiency is a number in [0, 1]. This module owns the only rules for moving
it: normalization to/from a skill's 0..level_scale scale, and the
evidence-weighted blend that folds a new observation into a prior. Pure and
deterministic — no DB, no clock, no model — so a proficiency change is always
reproducible and auditable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.enums import EvidenceSource

#: How far a single observation may move proficiency, so one noisy quiz cannot
#: swing a skill from 0 to 1.
DEFAULT_MAX_DELTA = 0.4

#: Base trust placed in an observation, before it is scaled by evidence
#: strength. Assessment evidence outweighs a completion, which outweighs a
#: self-report — assessments are the most objective signal we have.
EVIDENCE_BASE_WEIGHT: dict[EvidenceSource, float] = {
    EvidenceSource.ASSESSMENT: 0.75,
    EvidenceSource.COMPLETION: 0.45,
    EvidenceSource.INFERRED: 0.30,
    EvidenceSource.SELF_REPORT: 1.0,  # a self-report *is* the stated value
}

#: Question count at which an assessment carries its full weight. Fewer
#: questions → weaker evidence → a smaller move.
FULL_STRENGTH_QUESTION_COUNT = 8


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def proficiency_to_level(proficiency: float, level_scale: int) -> float:
    """Map [0, 1] proficiency onto a skill's 0..level_scale scale."""
    return round(clamp01(proficiency) * level_scale, 4)


def level_to_proficiency(level: float, level_scale: int) -> float:
    """Map a 0..level_scale level back to [0, 1] proficiency."""
    if level_scale <= 0:
        return 0.0
    return clamp01(level / level_scale)


def evidence_strength(question_count: int, *, full_at: int = FULL_STRENGTH_QUESTION_COUNT) -> float:
    """How much to trust an assessment of `question_count` questions, in [0, 1]."""
    if question_count <= 0:
        return 0.0
    return clamp01(question_count / full_at)


@dataclass(frozen=True, slots=True)
class ProficiencyUpdate:
    prior: float
    observed: float
    weight: float
    new_proficiency: float
    delta: float
    prior_confidence: float
    new_confidence: float


def blend_proficiency(
    prior: float,
    observed: float,
    *,
    weight: float,
    max_delta: float = DEFAULT_MAX_DELTA,
    prior_confidence: float = 0.5,
) -> ProficiencyUpdate:
    """Fold an observation into a prior proficiency.

    Moves `prior` toward `observed` by `weight` of the gap, capped at
    ±`max_delta` per event, then clamps to [0, 1]. Confidence rises toward the
    observation's weight but never falls (more evidence only sharpens belief).
    With weight 0 nothing changes; with weight 1 the result is `observed`
    (subject to the cap). Deterministic for identical inputs.
    """
    prior = clamp01(prior)
    observed = clamp01(observed)
    weight = clamp01(weight)

    raw_delta = weight * (observed - prior)
    delta = max(-max_delta, min(max_delta, raw_delta))
    new_proficiency = clamp01(prior + delta)

    prior_confidence = clamp01(prior_confidence)
    new_confidence = clamp01(prior_confidence + weight * (1.0 - prior_confidence))

    return ProficiencyUpdate(
        prior=prior,
        observed=observed,
        weight=weight,
        new_proficiency=round(new_proficiency, 6),
        delta=round(new_proficiency - prior, 6),
        prior_confidence=prior_confidence,
        new_confidence=round(new_confidence, 6),
    )


def observation_weight(
    source: EvidenceSource, *, strength: float = 1.0, max_weight: float = 1.0
) -> float:
    """Trust in an observation: its source's base weight scaled by strength."""
    base = EVIDENCE_BASE_WEIGHT.get(source, 0.5)
    return clamp01(min(max_weight, base * clamp01(strength)))


@dataclass(frozen=True, slots=True)
class SkillScore:
    """A per-skill result extracted from an assessment attempt."""

    skill_id: uuid.UUID
    correct: int
    total: int
    points_awarded: float
    points_possible: float

    @property
    def ratio(self) -> float:
        """Points-weighted score in [0, 1] (falls back to correct/total)."""
        if self.points_possible > 0:
            return clamp01(self.points_awarded / self.points_possible)
        if self.total > 0:
            return clamp01(self.correct / self.total)
        return 0.0


def assessment_skill_scores(
    responses: list[dict],
    *,
    fallback_skill_id: uuid.UUID | None = None,
) -> list[SkillScore]:
    """Group graded responses into a per-skill score.

    Each response is expected to carry `skill_id`, `is_correct`,
    `points_awarded` and (optionally) `points_possible`. Responses with no skill
    fall back to `fallback_skill_id` (the assessment's own skill). Skills are
    returned in a deterministic order (by id) so the caller's updates are stable.
    """
    buckets: dict[uuid.UUID, dict[str, float]] = {}
    for response in responses:
        raw_skill = response.get("skill_id") or fallback_skill_id
        if raw_skill is None:
            continue
        skill_id = raw_skill if isinstance(raw_skill, uuid.UUID) else uuid.UUID(str(raw_skill))

        bucket = buckets.setdefault(
            skill_id, {"correct": 0.0, "total": 0.0, "awarded": 0.0, "possible": 0.0}
        )
        bucket["total"] += 1
        bucket["correct"] += 1 if response.get("is_correct") else 0
        bucket["awarded"] += float(response.get("points_awarded") or 0.0)
        possible = response.get("points_possible")
        if possible is not None:
            bucket["possible"] += float(possible)

    return [
        SkillScore(
            skill_id=skill_id,
            correct=int(bucket["correct"]),
            total=int(bucket["total"]),
            points_awarded=bucket["awarded"],
            points_possible=bucket["possible"],
        )
        for skill_id, bucket in sorted(buckets.items(), key=lambda kv: str(kv[0]))
    ]

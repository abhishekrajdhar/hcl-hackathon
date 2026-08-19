"""SkillProficiencyUpdater — deterministic skill-proficiency updates.

The MVP rule from the spec, applied to assessment evidence:

    new_skill = 0.6 * old_skill + 0.4 * assessment_score

Pure and deterministic: no model, no randomness, no clock. Completed resources
apply a smaller, bounded nudge toward what the resource teaches; skips never
change proficiency.
"""

from __future__ import annotations

#: Weights of the MVP assessment update (must sum to 1).
OLD_WEIGHT = 0.6
SCORE_WEIGHT = 0.4
#: How much of the remaining gap a completed resource closes (bounded nudge).
COMPLETION_GAIN = 0.15


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def update_from_assessment(old_skill: float, assessment_score: float) -> float:
    """new = 0.6*old + 0.4*score, clamped to [0, 1]."""
    return clamp01(round(OLD_WEIGHT * clamp01(old_skill) + SCORE_WEIGHT * clamp01(assessment_score), 6))


def update_from_completion(old_skill: float, teaches_to: float) -> float:
    """A completed resource nudges proficiency toward the level it teaches to.

    Only ever raises proficiency, and never past what the resource covers.
    """
    old = clamp01(old_skill)
    target = clamp01(teaches_to)
    if target <= old:
        return old
    return clamp01(round(old + COMPLETION_GAIN * (target - old), 6))


def recover_previous(new_skill: float, assessment_score: float) -> float:
    """Invert the assessment update to recover the pre-update proficiency.

    Exact because the update is a fixed linear blend: given `new` and the
    `score`, `old = (new - 0.4*score) / 0.6`. Used to report the delta of an
    update already applied at submission time, without storing the prior value.
    """
    old = (clamp01(new_skill) - SCORE_WEIGHT * clamp01(assessment_score)) / OLD_WEIGHT
    return clamp01(round(old, 6))

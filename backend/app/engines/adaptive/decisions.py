"""Deterministic adaptive-path decisions from skill level and assessment score.

Encodes the spec's thresholds. Pure: given the numbers in, the same decisions
come out — no LLM, no heuristics beyond these fixed rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# --- skill-level bands ------------------------------------------------------
SKILL_SKIP_INTRO = 0.80          # skill > 0.80 -> skip introductory resources
SKILL_INTERMEDIATE_LOW = 0.60    # 0.60..0.80 -> intermediate resources
SKILL_REMEDIAL = 0.50            # skill < 0.50 -> prerequisite/remedial material

# --- assessment-score triggers ---------------------------------------------
SCORE_INSERT_REMEDIATION = 0.50  # score < 0.50 -> insert remediation resources
SCORE_UNLOCK_NEXT = 0.85         # score > 0.85 -> unlock next milestone

LevelBand = Literal["advanced", "intermediate", "foundational", "remedial"]


def level_band(skill_level: float) -> LevelBand:
    if skill_level > SKILL_SKIP_INTRO:
        return "advanced"
    if skill_level >= SKILL_INTERMEDIATE_LOW:
        return "intermediate"
    if skill_level >= SKILL_REMEDIAL:
        return "foundational"
    return "remedial"


@dataclass(frozen=True, slots=True)
class AdaptiveDecision:
    skill_level: float
    assessment_score: float | None
    band: LevelBand
    #: skill > 0.80 — the learner can skip introductory material.
    skip_introductory: bool
    #: skill < 0.50 — recommend prerequisite / remedial material.
    recommend_remedial: bool
    #: 0.60..0.80 — continue with intermediate resources.
    continue_intermediate: bool
    #: assessment score < 0.50 — insert remediation resources.
    insert_remediation: bool
    #: assessment score > 0.85 — unlock the next milestone.
    unlock_next_milestone: bool


def decide(skill_level: float, assessment_score: float | None = None) -> AdaptiveDecision:
    band = level_band(skill_level)
    return AdaptiveDecision(
        skill_level=skill_level,
        assessment_score=assessment_score,
        band=band,
        skip_introductory=skill_level > SKILL_SKIP_INTRO,
        recommend_remedial=skill_level < SKILL_REMEDIAL,
        continue_intermediate=SKILL_INTERMEDIATE_LOW <= skill_level <= SKILL_SKIP_INTRO,
        insert_remediation=assessment_score is not None and assessment_score < SCORE_INSERT_REMEDIATION,
        unlock_next_milestone=assessment_score is not None and assessment_score > SCORE_UNLOCK_NEXT,
    )

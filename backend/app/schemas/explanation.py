"""Recommendation explainability: structured evidence and explanations.

`RecommendationEvidence` is the ONLY thing the LLM is given. The explanation is
generated from these structured facts; a grounding check rejects any output that
introduces a number or skill not present in the evidence.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExplanationKind = Literal[
    "why_course", "why_now", "why_order", "why_project", "why_assessment"
]


class PrerequisiteRelation(BaseModel):
    skill: str
    relationship: str  # e.g. "hard_prerequisite"
    status: Literal["met", "unmet"]
    learner_level: float
    required_level: float


class ResourceSkillFact(BaseModel):
    skill: str
    teaches_from: float
    teaches_to: float


class RoadmapPosition(BaseModel):
    phase_index: int
    phase_title: str
    milestone: str
    unlocks: list[str] = Field(default_factory=list)


class RecommendationEvidence(BaseModel):
    """Structured, verifiable facts about one recommendation. No prose."""

    model_config = ConfigDict(from_attributes=True)

    #: Set when the evidence was assembled for a stored recommendation; None
    #: when it was assembled directly for a learning-path item.
    recommendation_id: uuid.UUID | None = None
    resource_title: str
    resource_type: str
    resource_difficulty: int
    learner_skill: str
    current_level: float
    required_level: float
    skill_gap: float
    prerequisite_relationships: list[PrerequisiteRelation] = Field(default_factory=list)
    resource_skills: list[ResourceSkillFact] = Field(default_factory=list)
    goal: str
    roadmap_position: RoadmapPosition | None = None
    #: Skills the learner already has at a solid level (context for "you already know…").
    strengths: list[str] = Field(default_factory=list)


class ExplanationRequest(BaseModel):
    kind: ExplanationKind = "why_course"
    #: Force the deterministic template instead of the LLM.
    use_llm: bool = True


class PathItemExplanationResponse(BaseModel):
    """Why one roadmap item is on the learner's path — grounded in the item's
    persisted rationale and the learner's current evidence, never invented."""

    item_id: uuid.UUID
    kind: ExplanationKind
    explanation: str
    grounded: bool
    source: Literal["llm", "template"]
    evidence: RecommendationEvidence


class ExplanationResponse(BaseModel):
    recommendation_id: uuid.UUID
    kind: ExplanationKind
    explanation: str
    #: True when the text passed the grounding check (no unsupported claims).
    grounded: bool
    source: Literal["llm", "template"]
    evidence: RecommendationEvidence

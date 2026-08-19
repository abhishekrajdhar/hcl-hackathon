"""Schemas for assessment generation and the enriched submit report."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import AssessmentResultRead


class GenerateAssessmentRequest(BaseModel):
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = Field(default=None, max_length=128)
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: int = Field(default=2, ge=1, le=5)
    title: str | None = Field(default=None, max_length=255)
    #: Force the deterministic template generator instead of the LLM.
    use_llm: bool = True


class GeneratedAssessmentInfo(BaseModel):
    assessment_id: uuid.UUID
    skill_id: uuid.UUID | None
    title: str
    question_count: int
    difficulty: int
    source: Literal["llm", "template"]
    source_model: str | None = None


class SkillUpdate(BaseModel):
    skill_id: uuid.UUID
    skill_name: str | None = None
    previous_proficiency: float
    new_proficiency: float
    delta: float


class WeakTopicRead(BaseModel):
    skill_id: uuid.UUID | None = None
    skill_name: str
    correct: int
    total: int
    ratio: float


class AssessmentSubmitReport(BaseModel):
    """Everything a learner sees after submitting: score, deterministic mastery
    mapping, per-skill proficiency updates, weak topics, and what to do next."""

    model_config = ConfigDict(from_attributes=True)

    result: AssessmentResultRead
    score: float
    percentage: float
    passed: bool
    mastery_level: Literal[
        "strong_mastery", "good_understanding", "partial_understanding", "requires_remediation"
    ]
    skill_updates: list[SkillUpdate] = Field(default_factory=list)
    weak_topics: list[WeakTopicRead] = Field(default_factory=list)
    recommended_next_action: str

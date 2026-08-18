from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssessmentType, QuestionType
from app.schemas.common import TimestampedModel


class QuestionBase(BaseModel):
    skill_id: uuid.UUID | None = None
    order_index: int = Field(ge=0)
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    stem: str = Field(min_length=1)
    options: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str | None = None
    points: float = Field(default=1.0, gt=0)
    difficulty_b: float = 0.0
    discrimination_a: float = 1.0


class QuestionCreate(QuestionBase):
    correct_answer: dict[str, Any] = Field(default_factory=dict)


class QuestionUpdate(BaseModel):
    order_index: int | None = Field(default=None, ge=0)
    question_type: QuestionType | None = None
    stem: str | None = Field(default=None, min_length=1)
    options: list[dict[str, Any]] | None = None
    correct_answer: dict[str, Any] | None = None
    explanation: str | None = None
    points: float | None = Field(default=None, gt=0)
    difficulty_b: float | None = None
    discrimination_a: float | None = None


class QuestionRead(QuestionBase, TimestampedModel):
    """Learner-facing view. Deliberately omits `correct_answer`."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: uuid.UUID


class QuestionAdminRead(QuestionRead):
    correct_answer: dict[str, Any] = Field(default_factory=dict)


class AssessmentBase(BaseModel):
    skill_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: AssessmentType = AssessmentType.CHECKPOINT
    difficulty: int = Field(default=1, ge=1, le=5)
    time_limit_seconds: int | None = Field(default=None, gt=0)
    passing_score: float = Field(default=0.7, ge=0, le=1)
    is_active: bool = True


class AssessmentCreate(AssessmentBase):
    questions: list[QuestionCreate] = Field(default_factory=list)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    type: AssessmentType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    time_limit_seconds: int | None = Field(default=None, gt=0)
    passing_score: float | None = Field(default=None, ge=0, le=1)
    is_active: bool | None = None


class AssessmentRead(AssessmentBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    is_generated: bool
    source_model: str | None = None
    question_count: int = 0


class AssessmentDetail(AssessmentRead):
    questions: list[QuestionRead] = Field(default_factory=list)


class AnswerSubmission(BaseModel):
    question_id: uuid.UUID
    response: Any = None
    time_spent_ms: int | None = Field(default=None, ge=0)


class AssessmentSubmission(BaseModel):
    path_item_id: uuid.UUID | None = None
    started_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    answers: list[AnswerSubmission] = Field(min_length=1)


class AssessmentResultRead(TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    assessment_id: uuid.UUID
    path_item_id: uuid.UUID | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float
    max_score: float
    percentage: float
    passed: bool
    theta_estimate: float | None = None
    duration_seconds: int | None = None
    responses: list[dict[str, Any]] = Field(default_factory=list)

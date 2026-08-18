from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GoalStatus
from app.schemas.common import TimestampedModel
from app.schemas.skill import SkillRead


class GoalSkillBase(BaseModel):
    skill_id: uuid.UUID
    required_level: float = Field(default=3.0, ge=0, le=10)
    importance: float = Field(default=1.0, ge=0, le=1)


class GoalSkillCreate(GoalSkillBase):
    pass


class GoalSkillUpdate(BaseModel):
    required_level: float | None = Field(default=None, ge=0, le=10)
    importance: float | None = Field(default=None, ge=0, le=1)


class GoalSkillRead(GoalSkillBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    goal_id: uuid.UUID
    skill: SkillRead | None = None


class LearningGoalBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    raw_input: str | None = None
    target_role: str | None = Field(default=None, max_length=255)
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = Field(default=3, ge=1, le=5)
    target_date: date | None = None


class LearningGoalCreate(LearningGoalBase):
    target_skills: list[GoalSkillCreate] = Field(default_factory=list)


class LearningGoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    raw_input: str | None = None
    target_role: str | None = Field(default=None, max_length=255)
    status: GoalStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    target_date: date | None = None


class LearningGoalRead(LearningGoalBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    target_skills: list[GoalSkillRead] = Field(default_factory=list)

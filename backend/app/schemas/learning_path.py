"""Schemas for the learning-path generator and roadmap views."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import PathItemStatus, PathStatus
from app.schemas.skill_gap import RequiredSkillInput


class GeneratePathRequest(BaseModel):
    user_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    target_skills: list[RequiredSkillInput] = Field(default_factory=list)
    goal_text: str | None = Field(default=None, max_length=2000)
    #: Overrides the learner profile's weekly hours / deadline when provided.
    weekly_hours: int | None = Field(default=None, ge=1, le=168)
    target_deadline: date | None = None
    #: Persist as the learner's active path (supersedes a prior active one).
    activate: bool = True


class RoadmapItem(BaseModel):
    id: uuid.UUID
    kind: str  # resource | assessment | project
    title: str
    status: PathItemStatus
    estimated_minutes: int
    resource_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    is_optional: bool = False


class RoadmapMilestone(BaseModel):
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None
    title: str
    current_level: float
    required_level: float
    gap: float
    prerequisites: list[str] = Field(default_factory=list)
    completion_criteria: str
    estimated_minutes: int
    resources: list[RoadmapItem] = Field(default_factory=list)
    assessment: RoadmapItem | None = None
    project: RoadmapItem | None = None


class RoadmapPhase(BaseModel):
    index: int
    title: str
    objective: str
    is_capstone: bool = False
    estimated_minutes: int
    planned_start: date | None = None
    planned_end: date | None = None
    milestones: list[RoadmapMilestone] = Field(default_factory=list)


class LearningPathRoadmap(BaseModel):
    path_id: uuid.UUID
    user_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    title: str
    version: int
    status: PathStatus
    generator_version: str | None = None
    total_estimated_minutes: int
    planned_start: date | None = None
    planned_end: date | None = None
    feasibility_ok: bool = True
    feasibility_warning: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    phases: list[RoadmapPhase] = Field(default_factory=list)
    created_at: datetime | None = None


class RegeneratePathRequest(BaseModel):
    weekly_hours: int | None = Field(default=None, ge=1, le=168)
    target_deadline: date | None = None

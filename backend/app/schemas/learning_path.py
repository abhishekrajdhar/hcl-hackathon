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
    """One planned item, carrying enough of its resource to be presented.

    The catalogue fields below are denormalised onto the item on purpose. The
    roadmap used to name a resource without saying where it lives, so a client
    could only show a link for the few items that also happened to come back
    from `/recommendations` — every other course in the plan was a dead title
    with no way to open it. `list_for_path` already eager-loads the resource,
    so this costs no extra query and can never go stale against the catalogue.
    """

    id: uuid.UUID
    kind: str  # resource | assessment | project
    title: str
    status: PathItemStatus
    estimated_minutes: int
    resource_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    is_optional: bool = False
    #: Where to actually go. None for assessments and in-app projects, which
    #: are taken inside the product rather than followed off-site.
    url: str | None = None
    provider: str | None = None
    description: str | None = None
    #: 1-5, or None where the item is not a catalogue resource.
    difficulty: int | None = None
    resource_type: str | None = None
    #: Skill names the resource teaches, and the skills it assumes.
    skills: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


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

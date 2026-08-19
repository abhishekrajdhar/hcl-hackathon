"""Request/response schemas for the skill-gap analysis endpoint.

Proficiencies are on the canonical [0, 1] scale, matching the learner profile.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkillRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str


class RequiredSkillInput(BaseModel):
    """A target skill and the proficiency the goal requires, in [0, 1]."""

    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None
    required_level: float = Field(ge=0, le=1)
    importance: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def _needs_reference(self) -> "RequiredSkillInput":
        if self.skill_id is None and not self.skill_slug:
            raise ValueError("Provide skill_id or skill_slug")
        return self


class CurrentSkillInput(BaseModel):
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None
    current_level: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _needs_reference(self) -> "CurrentSkillInput":
        if self.skill_id is None and not self.skill_slug:
            raise ValueError("Provide skill_id or skill_slug")
        return self


class SkillGapAnalyzeRequest(BaseModel):
    #: Pull the learner's current proficiencies from this user (self or admin).
    user_id: uuid.UUID | None = None
    #: Derive required skills from a goal's target vector.
    goal_id: uuid.UUID | None = None
    #: Or state required skills explicitly (overrides/supplements the goal).
    target_skills: list[RequiredSkillInput] = Field(default_factory=list)
    #: Explicit current proficiencies (override/supplement the user's).
    current_skills: list[CurrentSkillInput] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def _needs_required_and_current(self) -> "SkillGapAnalyzeRequest":
        if self.goal_id is None and not self.target_skills:
            raise ValueError("Provide goal_id or target_skills")
        if self.user_id is None and self.goal_id is None and not self.current_skills:
            raise ValueError("Provide user_id, goal_id, or current_skills for current levels")
        return self


class SkillGapItem(BaseModel):
    skill: SkillRef
    current_level: float
    required_level: float
    gap: float
    prerequisites: list[SkillRef] = Field(default_factory=list)
    priority: float
    rank: int
    level: int = Field(description="DAG layer; 0 = learnable immediately")
    is_target: bool
    importance: float
    downstream_count: int
    reason: str


class SkillGapAnalyzeResponse(BaseModel):
    user_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    total_gaps: int
    #: Gaps in prerequisite-aware learning order (not sorted by gap size).
    gaps: list[SkillGapItem] = Field(default_factory=list)
    #: Skills learnable right now, highest priority first.
    priority_skills: list[SkillRef] = Field(default_factory=list)
    #: Target skills already satisfied (gap <= 0).
    met_targets: list[SkillRef] = Field(default_factory=list)
    #: Requested skills that do not exist in the catalogue/graph.
    unknown_skills: list[str] = Field(default_factory=list)

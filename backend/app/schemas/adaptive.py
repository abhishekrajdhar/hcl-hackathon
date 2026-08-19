"""Schemas for the adaptive-learning update pipeline."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TriggerKind = Literal["assessment", "resource_completed", "resource_skipped", "explicit"]


class ExplicitSkillScore(BaseModel):
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None
    score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _needs_ref(self) -> "ExplicitSkillScore":
        if self.skill_id is None and not self.skill_slug:
            raise ValueError("Provide skill_id or skill_slug")
        return self


class AdaptiveUpdateRequest(BaseModel):
    user_id: uuid.UUID
    #: Exactly one trigger below.
    assessment_result_id: uuid.UUID | None = None
    completed_resource_id: uuid.UUID | None = None
    skipped_resource_id: uuid.UUID | None = None
    skill_scores: list[ExplicitSkillScore] = Field(default_factory=list)
    #: Optional context signals.
    feedback: str | None = Field(default=None, max_length=2000)
    time_spent_minutes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one_trigger(self) -> "AdaptiveUpdateRequest":
        triggers = [
            self.assessment_result_id is not None,
            self.completed_resource_id is not None,
            self.skipped_resource_id is not None,
            bool(self.skill_scores),
        ]
        if sum(triggers) != 1:
            raise ValueError(
                "Provide exactly one of: assessment_result_id, completed_resource_id, "
                "skipped_resource_id, skill_scores"
            )
        return self


class UpdatedSkillRead(BaseModel):
    skill_id: uuid.UUID
    skill_name: str | None = None
    previous_proficiency: float
    new_proficiency: float
    delta: float
    mastery_level: str
    level_band: Literal["advanced", "intermediate", "foundational", "remedial"]


class MilestoneRead(BaseModel):
    skill_id: uuid.UUID | None = None
    title: str
    phase_title: str
    phase_index: int


class ResourceItemRead(BaseModel):
    resource_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    title: str
    reason: str | None = None


class AdaptiveUpdateResponse(BaseModel):
    user_id: uuid.UUID
    trigger: TriggerKind
    updated_skills: list[UpdatedSkillRead] = Field(default_factory=list)
    completed_milestones: list[MilestoneRead] = Field(default_factory=list)
    unlocked_milestones: list[MilestoneRead] = Field(default_factory=list)
    removed_resources: list[ResourceItemRead] = Field(default_factory=list)
    newly_recommended_resources: list[ResourceItemRead] = Field(default_factory=list)
    next_recommended_action: str

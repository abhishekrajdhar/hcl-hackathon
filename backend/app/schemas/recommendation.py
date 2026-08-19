from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import RecommendationStatus
from app.schemas.common import TimestampedModel
from app.schemas.resource import ResourceRead
from app.schemas.skill_gap import RequiredSkillInput, SkillRef


class RecommendationCreate(BaseModel):
    """Admin/ingestion entry point. The ranking engine will populate these
    fields itself in a later phase."""

    resource_id: uuid.UUID
    skill_id: uuid.UUID | None = None
    path_id: uuid.UUID | None = None
    score: float = Field(default=0.0, ge=0)
    rank: int = Field(default=0, ge=0)
    reason: str | None = None
    rationale_trace: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None


class RecommendationStatusUpdate(BaseModel):
    status: RecommendationStatus


class RecommendationRead(TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    resource_id: uuid.UUID
    skill_id: uuid.UUID | None
    path_id: uuid.UUID | None
    score: float
    rank: int
    status: RecommendationStatus
    reason: str | None
    rationale_trace: dict[str, Any]
    generated_at: datetime
    expires_at: datetime | None
    responded_at: datetime | None
    resource: ResourceRead | None = None


# --- ranking engine (POST /api/recommendations) ----------------------------
class RecommendationRequest(BaseModel):
    """What to recommend for whom.

    A goal is required, expressed as any of: a stored goal (`goal_id`), an
    explicit required-skill list, or a single `optional_skill` to focus on.
    `goal_text` is optional free text that enriches the semantic query.
    """

    user_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    target_skills: list[RequiredSkillInput] = Field(default_factory=list)
    goal_text: str | None = Field(default=None, max_length=2000)
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = Field(default=None, max_length=128)
    top_k: int = Field(default=10, ge=1, le=50)
    #: Include resources the learner is not yet ready for (demoted, flagged).
    include_unready: bool = False
    #: Persist the ranked results as pending Recommendation rows.
    persist: bool = False

    @model_validator(mode="after")
    def _needs_a_goal(self) -> "RecommendationRequest":
        if (
            self.goal_id is None
            and not self.target_skills
            and self.skill_id is None
            and not self.skill_slug
        ):
            raise ValueError("Provide goal_id, target_skills, or an optional skill")
        return self


class RecommendationItem(BaseModel):
    resource: ResourceRead
    score: float = Field(ge=0, le=1)
    rank: int
    is_ready: bool
    #: Each hybrid-score factor, normalised to [0, 1].
    factors: dict[str, float] = Field(default_factory=dict)
    #: Each factor's weighted contribution to the score.
    contributions: dict[str, float] = Field(default_factory=dict)
    matched_skills: list[SkillRef] = Field(default_factory=list)
    unmet_prerequisites: list[SkillRef] = Field(default_factory=list)
    reason: str


class RecommendationResponse(BaseModel):
    user_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    count: int
    #: How many candidates were gated out as not-yet-appropriate.
    excluded_unready: int = 0
    weights: dict[str, float] = Field(default_factory=dict)
    recommendations: list[RecommendationItem] = Field(default_factory=list)

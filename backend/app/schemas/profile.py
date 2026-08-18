from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExperienceLevel
from app.schemas.common import TimestampedModel


class LearnerProfileBase(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    goal_text_raw: str | None = None
    experience_level: ExperienceLevel = ExperienceLevel.BEGINNER
    weekly_hours: int = Field(default=5, ge=0, le=168)
    target_deadline: date | None = None
    preferred_modalities: list[str] = Field(default_factory=list)
    preferred_languages: list[str] = Field(default_factory=lambda: ["en"])
    learning_style: str | None = Field(default=None, max_length=64)
    budget_ceiling: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    extra: dict[str, Any] = Field(default_factory=dict)


class LearnerProfileCreate(LearnerProfileBase):
    pass


class LearnerProfileUpdate(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    goal_text_raw: str | None = None
    experience_level: ExperienceLevel | None = None
    weekly_hours: int | None = Field(default=None, ge=0, le=168)
    target_deadline: date | None = None
    preferred_modalities: list[str] | None = None
    preferred_languages: list[str] | None = None
    learning_style: str | None = Field(default=None, max_length=64)
    budget_ceiling: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    extra: dict[str, Any] | None = None


class LearnerProfileRead(LearnerProfileBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    extraction_confidence: float | None
    extraction_model: str | None
    version: int

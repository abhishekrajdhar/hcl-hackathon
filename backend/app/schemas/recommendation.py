from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecommendationStatus
from app.schemas.common import TimestampedModel
from app.schemas.resource import ResourceRead


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

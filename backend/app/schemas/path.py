from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PathItemStatus, PathItemType, PathStatus
from app.schemas.common import TimestampedModel
from app.schemas.resource import ResourceRead


class PathItemBase(BaseModel):
    resource_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    order_index: int = Field(ge=0)
    milestone_index: int = Field(default=0, ge=0)
    milestone_title: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    item_type: PathItemType = PathItemType.RESOURCE
    status: PathItemStatus = PathItemStatus.LOCKED
    estimated_minutes: int = Field(default=0, ge=0)
    is_optional: bool = False
    score: float | None = None
    rationale_trace: dict[str, Any] = Field(default_factory=dict)
    planned_start: date | None = None
    planned_end: date | None = None


class PathItemCreate(PathItemBase):
    pass


class PathItemUpdate(BaseModel):
    order_index: int | None = Field(default=None, ge=0)
    milestone_index: int | None = Field(default=None, ge=0)
    milestone_title: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=512)
    status: PathItemStatus | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    is_optional: bool | None = None
    planned_start: date | None = None
    planned_end: date | None = None


class PathItemRead(PathItemBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    path_id: uuid.UUID
    completed_at: datetime | None = None
    resource: ResourceRead | None = None


class LearningPathBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    goal_id: uuid.UUID | None = None
    status: PathStatus = PathStatus.DRAFT
    generator_version: str | None = Field(default=None, max_length=32)
    constraints_snapshot: dict[str, Any] = Field(default_factory=dict)


class LearningPathCreate(LearningPathBase):
    items: list[PathItemCreate] = Field(default_factory=list)


class LearningPathUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: PathStatus | None = None


class LearningPathRead(LearningPathBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    version: int
    supersedes_path_id: uuid.UUID | None = None
    total_estimated_minutes: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LearningPathDetail(LearningPathRead):
    items: list[PathItemRead] = Field(default_factory=list)

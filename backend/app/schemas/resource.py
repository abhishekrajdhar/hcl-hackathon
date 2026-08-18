from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.enums import Modality, ResourceType
from app.schemas.common import TimestampedModel
from app.schemas.skill import SkillRead


class ResourceSkillBase(BaseModel):
    skill_id: uuid.UUID
    teaches_level_from: float = Field(default=0.0, ge=0, le=10)
    teaches_level_to: float = Field(default=3.0, ge=0, le=10)
    coverage_weight: float = Field(default=1.0, ge=0, le=1)
    is_primary: bool = False


class ResourceSkillCreate(ResourceSkillBase):
    pass


class ResourceSkillUpdate(BaseModel):
    teaches_level_from: float | None = Field(default=None, ge=0, le=10)
    teaches_level_to: float | None = Field(default=None, ge=0, le=10)
    coverage_weight: float | None = Field(default=None, ge=0, le=1)
    is_primary: bool | None = None


class ResourceSkillRead(ResourceSkillBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    resource_id: uuid.UUID
    skill: SkillRead | None = None


class ResourceBase(BaseModel):
    provider: str = Field(min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    url: HttpUrl
    type: ResourceType = ResourceType.COURSE
    modality: Modality = Modality.MIXED
    difficulty: int = Field(default=1, ge=1, le=5)
    duration_minutes: int = Field(default=0, ge=0)
    cost: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    language: str = Field(default="en", max_length=16)
    rating: float | None = Field(default=None, ge=0, le=5)
    rating_count: int = Field(default=0, ge=0)
    published_at: datetime | None = None
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class ResourceCreate(ResourceBase):
    skills: list[ResourceSkillCreate] = Field(default_factory=list)


class ResourceUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    url: HttpUrl | None = None
    type: ResourceType | None = None
    modality: Modality | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    duration_minutes: int | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    language: str | None = Field(default=None, max_length=16)
    rating: float | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None


class ResourceRead(ResourceBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    url: str  # stored as text; not re-validated as HttpUrl on read
    skills: list[ResourceSkillRead] = Field(default_factory=list)

    @field_validator("url", mode="before")
    @classmethod
    def _stringify_url(cls, value: Any) -> Any:
        return str(value) if value is not None else value

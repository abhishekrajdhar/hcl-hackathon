from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

from app.models.enums import Modality, ResourceType
from app.schemas.common import TimestampedModel
from app.schemas.skill import SkillRead


# --- taught skills ---------------------------------------------------------
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


# --- prerequisites ---------------------------------------------------------
class ResourcePrerequisiteBase(BaseModel):
    skill_id: uuid.UUID
    min_proficiency: float = Field(default=0.0, ge=0, le=1)


class ResourcePrerequisiteCreate(ResourcePrerequisiteBase):
    pass


class ResourcePrerequisiteRead(ResourcePrerequisiteBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    resource_id: uuid.UUID
    skill: SkillRead | None = None


# --- resource --------------------------------------------------------------
class ResourceBase(BaseModel):
    # `metadata` is exposed at the API; it maps to the ORM attribute `extra`
    # (SQLAlchemy reserves `metadata`). populate_by_name lets callers send
    # either key, and FastAPI serialises responses by alias -> "metadata".
    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    url: HttpUrl
    resource_type: ResourceType = ResourceType.COURSE
    modality: Modality = Modality.MIXED
    difficulty: int = Field(default=1, ge=1, le=5)
    estimated_hours: float = Field(default=0.0, ge=0, le=10000)
    quality_score: float | None = Field(default=None, ge=0, le=1)
    rating: float | None = Field(default=None, ge=0, le=5)
    rating_count: int = Field(default=0, ge=0)
    cost: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    language: str = Field(default="en", max_length=16)
    published_at: datetime | None = None
    is_active: bool = True
    extra: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "extra"),
        serialization_alias="metadata",
    )


class ResourceCreate(ResourceBase):
    skills: list[ResourceSkillCreate] = Field(default_factory=list)
    prerequisites: list[ResourcePrerequisiteCreate] = Field(default_factory=list)


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str | None = Field(default=None, min_length=1, max_length=128)
    external_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    url: HttpUrl | None = None
    resource_type: ResourceType | None = None
    modality: Modality | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    estimated_hours: float | None = Field(default=None, ge=0, le=10000)
    quality_score: float | None = Field(default=None, ge=0, le=1)
    rating: float | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    language: str | None = Field(default=None, max_length=16)
    published_at: datetime | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "extra"),
        serialization_alias="metadata",
    )
    #: When provided on PUT, these collections are replaced wholesale.
    skills: list[ResourceSkillCreate] | None = None
    prerequisites: list[ResourcePrerequisiteCreate] | None = None


class ResourceRead(ResourceBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    url: str  # stored as text; not re-validated as HttpUrl on read
    # Read the ORM `.extra` attribute by field name; only the output is aliased
    # to `metadata`. A validation alias of "metadata" would resolve to the
    # SQLAlchemy MetaData object on the model instead.
    extra: dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    skills: list[ResourceSkillRead] = Field(default_factory=list)
    prerequisites: list[ResourcePrerequisiteRead] = Field(default_factory=list)

    @field_validator("url", mode="before")
    @classmethod
    def _stringify_url(cls, value: Any) -> Any:
        return str(value) if value is not None else value

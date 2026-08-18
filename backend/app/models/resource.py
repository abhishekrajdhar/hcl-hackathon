"""Learning resources, the skills they teach, and their prerequisites."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import Modality, ResourceType
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.skill import Skill


class Resource(UUIDMixin, TimestampMixin, Base):
    """Something a learner can use to develop a skill.

    Deliberately provider-agnostic: `provider` + `external_id` identify the
    upstream record so a real catalogue (Coursera, YouTube, …) can be ingested
    later without schema changes, while today the rows are hand-seeded with
    mock URLs.
    """

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_resources_provider_external_id"),
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="difficulty_range"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)", name="rating_range"
        ),
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
            name="quality_score_range",
        ),
        CheckConstraint("estimated_hours >= 0", name="estimated_hours_non_negative"),
        Index("ix_resources_resource_type_difficulty", "resource_type", "difficulty"),
    )

    external_id: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    resource_type: Mapped[ResourceType] = mapped_column(
        pg_enum(ResourceType, "resource_type"),
        nullable=False,
        default=ResourceType.COURSE,
    )
    modality: Mapped[Modality] = mapped_column(
        pg_enum(Modality, "modality"), nullable=False, default=Modality.MIXED
    )
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Estimated time to complete, in hours (fractional allowed).
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Curated/computed quality in [0, 1], distinct from the crowd `rating`.
    #: Nullable = not yet scored.
    quality_score: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM))
    #: Flexible provider-specific bag. Exposed at the API as `metadata` (the ORM
    #: attribute is `extra` because `metadata` is reserved by SQLAlchemy).
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    skills: Mapped[list["ResourceSkill"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    prerequisites: Mapped[list["ResourcePrerequisite"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Resource {self.title[:40]}>"


class ResourceSkill(UUIDMixin, TimestampMixin, Base):
    """Which skill a resource teaches, and across which mastery band."""

    __tablename__ = "resource_skills"
    __table_args__ = (
        UniqueConstraint("resource_id", "skill_id", name="uq_resource_skills_resource_id_skill_id"),
        CheckConstraint(
            "teaches_level_to > teaches_level_from", name="teaches_level_band_ordered"
        ),
        CheckConstraint(
            "coverage_weight >= 0 AND coverage_weight <= 1", name="coverage_weight_range"
        ),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teaches_level_from: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    teaches_level_to: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    coverage_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    resource: Mapped["Resource"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship()


class ResourcePrerequisite(UUIDMixin, TimestampMixin, Base):
    """A skill the learner should already have before using the resource.

    Distinct from `ResourceSkill` (what the resource *teaches*); this is what it
    *assumes*. `min_proficiency` is on the canonical [0, 1] scale so it lines up
    with the learner profile's proficiency vector for readiness checks.
    """

    __tablename__ = "resource_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "resource_id", "skill_id", name="uq_resource_prerequisites_resource_id_skill_id"
        ),
        CheckConstraint(
            "min_proficiency >= 0 AND min_proficiency <= 1", name="min_proficiency_range"
        ),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    min_proficiency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    resource: Mapped["Resource"] = relationship(back_populates="prerequisites")
    skill: Mapped["Skill"] = relationship()

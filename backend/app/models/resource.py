"""Learning resources and the skills they teach."""

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
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_resources_provider_external_id"),
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="difficulty_range"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)", name="rating_range"
        ),
        CheckConstraint("duration_minutes >= 0", name="duration_non_negative"),
        Index("ix_resources_type_difficulty", "type", "difficulty"),
    )

    external_id: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[ResourceType] = mapped_column(
        pg_enum(ResourceType, "resource_type"), nullable=False, default=ResourceType.COURSE
    )
    modality: Mapped[Modality] = mapped_column(
        pg_enum(Modality, "modality"), nullable=False, default=Modality.MIXED
    )
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    rating: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    skills: Mapped[list["ResourceSkill"]] = relationship(
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

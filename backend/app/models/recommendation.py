"""Persisted recommendations produced by the ranking stage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.enums import RecommendationStatus
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.resource import Resource
    from app.models.skill import Skill
    from app.models.user import User


class Recommendation(UUIDMixin, TimestampMixin, Base):
    """A scored resource suggestion.

    `rationale_trace` carries the feature contributions that produced `score`.
    It is the sole input to the (future) explanation stage.
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("rank >= 0", name="rank_non_negative"),
        Index("ix_recommendations_user_id_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), index=True
    )
    path_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_paths.id", ondelete="SET NULL")
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RecommendationStatus] = mapped_column(
        pg_enum(RecommendationStatus, "recommendation_status"),
        nullable=False,
        default=RecommendationStatus.PENDING,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    rationale_trace: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="recommendations")
    resource: Mapped["Resource"] = relationship()
    skill: Mapped["Skill | None"] = relationship()

"""Learner feedback on any recommendable entity."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import FeedbackSignal, FeedbackTargetType
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.user import User


class Feedback(UUIDMixin, TimestampMixin, Base):
    """Polymorphic by (target_type, target_id) — deliberately not a hard FK,
    because the target may be any of several tables."""

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"),
        Index("ix_feedback_target_type_target_id", "target_type", "target_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[FeedbackTargetType] = mapped_column(
        pg_enum(FeedbackTargetType, "feedback_target_type"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    signal: Mapped[FeedbackSignal] = mapped_column(
        pg_enum(FeedbackSignal, "feedback_signal"), nullable=False
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="feedback_entries")

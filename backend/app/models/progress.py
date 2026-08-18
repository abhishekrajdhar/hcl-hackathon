"""Append-only progress event log."""

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.enums import ProgressEventType
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.user import User


class UserProgress(UUIDMixin, TimestampMixin, Base):
    """Progress is event-sourced: every view is derived from these rows."""

    __tablename__ = "user_progress"
    __table_args__ = (
        CheckConstraint("progress_pct >= 0 AND progress_pct <= 100", name="progress_pct_range"),
        CheckConstraint("time_spent_minutes >= 0", name="time_spent_non_negative"),
        Index("ix_user_progress_user_id_occurred_at", "user_id", "occurred_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_path_items.id", ondelete="CASCADE"), index=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[ProgressEventType] = mapped_column(
        pg_enum(ProgressEventType, "progress_event_type"), nullable=False
    )
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_spent_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="progress_events")

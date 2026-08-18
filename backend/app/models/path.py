"""Generated learning paths and their ordered items."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PathItemStatus, PathItemType, PathStatus
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.goal import LearningGoal
    from app.models.resource import Resource
    from app.models.user import User


class LearningPath(UUIDMixin, TimestampMixin, Base):
    """An immutable, versioned plan. Revisions create a new row, never mutate."""

    __tablename__ = "learning_paths"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_learning_paths_user_id_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_goals.id", ondelete="SET NULL"), index=True
    )
    supersedes_path_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_paths.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[PathStatus] = mapped_column(
        pg_enum(PathStatus, "path_status"), nullable=False, default=PathStatus.DRAFT
    )
    generator_version: Mapped[str | None] = mapped_column(String(32))
    constraints_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="paths")
    goal: Mapped["LearningGoal | None"] = relationship(back_populates="paths")
    items: Mapped[list["LearningPathItem"]] = relationship(
        back_populates="path",
        cascade="all, delete-orphan",
        order_by="LearningPathItem.order_index",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LearningPath {self.title} v{self.version}>"


class LearningPathItem(UUIDMixin, TimestampMixin, Base):
    """One step of a path. Milestones are expressed as a grouping index."""

    __tablename__ = "learning_path_items"
    __table_args__ = (
        UniqueConstraint("path_id", "order_index", name="uq_learning_path_items_path_id_order_index"),
        CheckConstraint("order_index >= 0", name="order_index_non_negative"),
        CheckConstraint(
            "resource_id IS NOT NULL OR assessment_id IS NOT NULL",
            name="item_targets_resource_or_assessment",
        ),
        Index("ix_learning_path_items_path_id_milestone_index", "path_id", "milestone_index"),
    )

    path_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL"), index=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    milestone_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    milestone_title: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    item_type: Mapped[PathItemType] = mapped_column(
        pg_enum(PathItemType, "path_item_type"), nullable=False, default=PathItemType.RESOURCE
    )
    status: Mapped[PathItemStatus] = mapped_column(
        pg_enum(PathItemStatus, "path_item_status"), nullable=False, default=PathItemStatus.LOCKED
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[float | None] = mapped_column(Float)
    # Feature contributions from the ranking stage. The explanation layer reads
    # this and is not permitted to invent anything outside it.
    rationale_trace: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    path: Mapped["LearningPath"] = relationship(back_populates="items")
    resource: Mapped["Resource | None"] = relationship()
    assessment: Mapped["Assessment | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LearningPathItem #{self.order_index} {self.title[:32]}>"

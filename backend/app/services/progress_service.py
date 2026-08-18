from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.enums import PathItemStatus, ProgressEventType
from app.models.progress import UserProgress
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.progress import UserProgressRepository
from app.repositories.resource import ResourceRepository
from app.schemas.progress import ProgressEventCreate, ProgressSummary
from app.services.base import BaseService


class ProgressService(BaseService):
    """Progress is an append-only event log; summaries are always derived."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.events = UserProgressRepository(session)
        self.items = LearningPathItemRepository(session)
        self.paths = LearningPathRepository(session)
        self.resources = ResourceRepository(session)

    async def record(self, user_id: uuid.UUID, payload: ProgressEventCreate) -> UserProgress:
        if payload.path_item_id is None and payload.resource_id is None:
            raise ValidationError(
                "A progress event must reference a path item or a resource",
                error_code="target_required",
            )

        item = None
        if payload.path_item_id is not None:
            item = await self.items.get(payload.path_item_id)
            if item is None:
                raise NotFoundError("Learning path item", payload.path_item_id)
            path = await self.paths.get(item.path_id)
            if path is None or path.user_id != user_id:
                raise NotFoundError("Learning path item", payload.path_item_id)

        if payload.resource_id is not None and await self.resources.get(payload.resource_id) is None:
            raise NotFoundError("Resource", payload.resource_id)

        event = await self.events.create(
            {
                **payload.model_dump(exclude={"occurred_at"}),
                "user_id": user_id,
                "occurred_at": payload.occurred_at or datetime.now(timezone.utc),
            }
        )

        # Keep the denormalised item status in step with the event stream.
        if item is not None:
            if payload.event_type == ProgressEventType.COMPLETED:
                item.status = PathItemStatus.COMPLETED
                item.completed_at = event.occurred_at
            elif payload.event_type == ProgressEventType.STARTED:
                if item.status in (PathItemStatus.LOCKED, PathItemStatus.AVAILABLE):
                    item.status = PathItemStatus.IN_PROGRESS
            elif payload.event_type == ProgressEventType.SKIPPED:
                item.status = PathItemStatus.SKIPPED
            await self.session.flush()

        await self.commit()
        return event

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[UserProgress], int]:
        items = await self.events.list_for_user(user_id, limit=limit, offset=offset)
        total = await self.events.count([UserProgress.user_id == user_id])
        return items, total

    async def summary(self, user_id: uuid.UUID) -> ProgressSummary:
        aggregate = await self.events.aggregate_for_user(user_id)

        active_path = await self.paths.get_active_for_user(user_id)
        total_items = 0
        completed_items = 0
        completion_pct = 0.0
        if active_path is not None:
            path_items = await self.items.list_for_path(active_path.id)
            total_items = len(path_items)
            completed_ids = await self.events.completed_item_ids(user_id, active_path.id)
            completed_items = len(completed_ids)
            if total_items:
                completion_pct = round(completed_items / total_items * 100, 2)

        return ProgressSummary(
            user_id=user_id,
            total_events=int(aggregate["total_events"]),  # type: ignore[arg-type]
            items_started=int(aggregate["items_started"]),  # type: ignore[arg-type]
            items_completed=int(aggregate["items_completed"]),  # type: ignore[arg-type]
            total_time_minutes=int(aggregate["total_time_minutes"]),  # type: ignore[arg-type]
            active_path_id=active_path.id if active_path else None,
            active_path_total_items=total_items,
            active_path_completed_items=completed_items,
            completion_pct=completion_pct,
            last_activity_at=aggregate["last_activity_at"],  # type: ignore[arg-type]
        )

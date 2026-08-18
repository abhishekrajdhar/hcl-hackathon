from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import distinct, func, select

from app.models.enums import ProgressEventType
from app.models.progress import UserProgress
from app.repositories.base import BaseRepository


class UserProgressRepository(BaseRepository[UserProgress]):
    model = UserProgress

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[UserProgress]:
        stmt = (
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .order_by(UserProgress.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def aggregate_for_user(self, user_id: uuid.UUID) -> dict[str, object]:
        """One round trip for every scalar the summary needs."""
        started = func.count(distinct(UserProgress.path_item_id)).filter(
            UserProgress.event_type == ProgressEventType.STARTED
        )
        completed = func.count(distinct(UserProgress.path_item_id)).filter(
            UserProgress.event_type == ProgressEventType.COMPLETED
        )
        stmt = select(
            func.count(UserProgress.id),
            started,
            completed,
            func.coalesce(func.sum(UserProgress.time_spent_minutes), 0),
            func.max(UserProgress.occurred_at),
        ).where(UserProgress.user_id == user_id)

        row = (await self.session.execute(stmt)).one()
        return {
            "total_events": int(row[0]),
            "items_started": int(row[1] or 0),
            "items_completed": int(row[2] or 0),
            "total_time_minutes": int(row[3] or 0),
            "last_activity_at": row[4],
        }

    async def completed_item_ids(self, user_id: uuid.UUID, path_id: uuid.UUID) -> set[uuid.UUID]:
        from app.models.path import LearningPathItem

        stmt = (
            select(distinct(UserProgress.path_item_id))
            .join(LearningPathItem, LearningPathItem.id == UserProgress.path_item_id)
            .where(
                UserProgress.user_id == user_id,
                LearningPathItem.path_id == path_id,
                UserProgress.event_type == ProgressEventType.COMPLETED,
            )
        )
        return {row[0] for row in await self.session.execute(stmt) if row[0] is not None}

    async def last_activity(self, user_id: uuid.UUID) -> datetime | None:
        stmt = select(func.max(UserProgress.occurred_at)).where(UserProgress.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

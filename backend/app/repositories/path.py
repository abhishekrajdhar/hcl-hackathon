from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.models.enums import PathStatus
from app.models.path import LearningPath, LearningPathItem
from app.repositories.base import BaseRepository


class LearningPathRepository(BaseRepository[LearningPath]):
    model = LearningPath

    def with_items(self) -> Select[tuple[LearningPath]]:
        return select(LearningPath).options(
            selectinload(LearningPath.items).selectinload(LearningPathItem.resource)
        )

    async def get_with_items(self, path_id: uuid.UUID) -> LearningPath | None:
        stmt = self.with_items().where(LearningPath.id == path_id)
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def get_active_for_user(self, user_id: uuid.UUID) -> LearningPath | None:
        stmt = (
            self.with_items()
            .where(LearningPath.user_id == user_id, LearningPath.status == PathStatus.ACTIVE)
            .order_by(LearningPath.version.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def next_version(self, user_id: uuid.UUID, goal_id: uuid.UUID | None) -> int:
        stmt = select(func.coalesce(func.max(LearningPath.version), 0)).where(
            LearningPath.user_id == user_id
        )
        stmt = stmt.where(
            LearningPath.goal_id == goal_id if goal_id is not None else LearningPath.goal_id.is_(None)
        )
        return int((await self.session.execute(stmt)).scalar_one()) + 1


class LearningPathItemRepository(BaseRepository[LearningPathItem]):
    model = LearningPathItem

    async def list_for_path(self, path_id: uuid.UUID) -> list[LearningPathItem]:
        stmt = (
            select(LearningPathItem)
            .where(LearningPathItem.path_id == path_id)
            .order_by(LearningPathItem.order_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def max_order_index(self, path_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(LearningPathItem.order_index), -1)).where(
            LearningPathItem.path_id == path_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def total_minutes(self, path_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.sum(LearningPathItem.estimated_minutes), 0)).where(
            LearningPathItem.path_id == path_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

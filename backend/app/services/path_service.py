"""Learning path CRUD.

Path *generation* (sequencing, set cover, scheduling) is a later phase; this
service only manages hand-authored or externally supplied paths and enforces
the ownership and ordering invariants those paths must satisfy.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import PathItemStatus, PathStatus
from app.models.path import LearningPath, LearningPathItem
from app.repositories.assessment import AssessmentRepository
from app.repositories.goal import LearningGoalRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.resource import ResourceRepository
from app.schemas.path import (
    LearningPathCreate,
    LearningPathUpdate,
    PathItemCreate,
    PathItemUpdate,
)
from app.services.base import BaseService


class PathService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.paths = LearningPathRepository(session)
        self.items = LearningPathItemRepository(session)
        self.resources = ResourceRepository(session)
        self.assessments = AssessmentRepository(session)
        self.goals = LearningGoalRepository(session)

    async def get_owned(self, path_id: uuid.UUID, user_id: uuid.UUID) -> LearningPath:
        path = await self.paths.get_with_items(path_id)
        if path is None or path.user_id != user_id:
            raise NotFoundError("Learning path", path_id)
        return path

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int, status: PathStatus | None = None
    ) -> tuple[list[LearningPath], int]:
        filters = [LearningPath.user_id == user_id]
        if status:
            filters.append(LearningPath.status == status)
        items = await self.paths.list(
            limit=limit, offset=offset, filters=filters, order_by=(LearningPath.created_at.desc(),)
        )
        total = await self.paths.count(filters)
        return items, total

    async def get_active(self, user_id: uuid.UUID) -> LearningPath:
        path = await self.paths.get_active_for_user(user_id)
        if path is None:
            raise NotFoundError("Active learning path for this user")
        return path

    async def create(self, user_id: uuid.UUID, payload: LearningPathCreate) -> LearningPath:
        if payload.goal_id is not None:
            goal = await self.goals.get(payload.goal_id)
            if goal is None or goal.user_id != user_id:
                raise NotFoundError("Learning goal", payload.goal_id)

        version = await self.paths.next_version(user_id, payload.goal_id)
        path = await self.paths.create(
            {
                **payload.model_dump(exclude={"items"}),
                "user_id": user_id,
                "version": version,
            }
        )

        seen_order: set[int] = set()
        total_minutes = 0
        for item in payload.items:
            await self._validate_item(item)
            if item.order_index in seen_order:
                raise ValidationError(
                    f"Duplicate order_index {item.order_index} in path items",
                    error_code="duplicate_order_index",
                )
            seen_order.add(item.order_index)
            total_minutes += item.estimated_minutes
            self.items.add(LearningPathItem(path_id=path.id, **item.model_dump()))

        path.total_estimated_minutes = total_minutes
        await self.session.flush()
        await self.commit()
        return await self.get_owned(path.id, user_id)

    async def _validate_item(self, item: PathItemCreate | LearningPathItem) -> None:
        if item.resource_id is None and item.assessment_id is None:
            raise ValidationError(
                "A path item must reference either a resource or an assessment",
                error_code="item_target_required",
            )
        if item.resource_id is not None and await self.resources.get(item.resource_id) is None:
            raise NotFoundError("Resource", item.resource_id)
        if item.assessment_id is not None and await self.assessments.get(item.assessment_id) is None:
            raise NotFoundError("Assessment", item.assessment_id)

    async def update(
        self, path_id: uuid.UUID, user_id: uuid.UUID, payload: LearningPathUpdate
    ) -> LearningPath:
        path = await self.get_owned(path_id, user_id)
        data = payload.model_dump(exclude_unset=True)

        new_status = data.get("status")
        if new_status == PathStatus.ACTIVE and path.status != PathStatus.ACTIVE:
            await self._deactivate_others(user_id, path.id)
            data.setdefault("started_at", datetime.now(timezone.utc))
        if new_status == PathStatus.COMPLETED:
            data.setdefault("completed_at", datetime.now(timezone.utc))

        await self.paths.update(path, data)
        await self.commit()
        return await self.get_owned(path_id, user_id)

    async def _deactivate_others(self, user_id: uuid.UUID, keep_path_id: uuid.UUID) -> None:
        """Exactly one active path per learner."""
        active = await self.paths.list(
            limit=100,
            filters=[
                LearningPath.user_id == user_id,
                LearningPath.status == PathStatus.ACTIVE,
                LearningPath.id != keep_path_id,
            ],
        )
        for other in active:
            other.status = PathStatus.SUPERSEDED
        await self.session.flush()

    async def delete(self, path_id: uuid.UUID, user_id: uuid.UUID) -> None:
        path = await self.get_owned(path_id, user_id)
        await self.paths.delete(path)
        await self.commit()

    # --- items ------------------------------------------------------------
    async def list_items(self, path_id: uuid.UUID, user_id: uuid.UUID) -> list[LearningPathItem]:
        await self.get_owned(path_id, user_id)
        return await self.items.list_for_path(path_id)

    async def add_item(
        self, path_id: uuid.UUID, user_id: uuid.UUID, payload: PathItemCreate
    ) -> LearningPathItem:
        await self.get_owned(path_id, user_id)
        await self._validate_item(payload)

        data = payload.model_dump()
        existing = await self.items.get_by(path_id=path_id, order_index=payload.order_index)
        if existing is not None:
            raise ConflictError(
                f"order_index {payload.order_index} is already used in this path",
                error_code="duplicate_order_index",
            )

        item = await self.items.create({**data, "path_id": path_id})
        await self._recalculate_total(path_id)
        await self.commit()
        return await self._reload_item(item.id)

    async def update_item(
        self,
        path_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: PathItemUpdate,
    ) -> LearningPathItem:
        await self.get_owned(path_id, user_id)
        item = await self.items.get(item_id)
        if item is None or item.path_id != path_id:
            raise NotFoundError("Learning path item", item_id)

        data = payload.model_dump(exclude_unset=True)
        new_order = data.get("order_index")
        if new_order is not None and new_order != item.order_index:
            clash = await self.items.get_by(path_id=path_id, order_index=new_order)
            if clash is not None:
                raise ConflictError(
                    f"order_index {new_order} is already used in this path",
                    error_code="duplicate_order_index",
                )
        if data.get("status") == PathItemStatus.COMPLETED and item.completed_at is None:
            data["completed_at"] = datetime.now(timezone.utc)

        await self.items.update(item, data)
        await self._recalculate_total(path_id)
        await self.commit()
        return await self._reload_item(item.id)

    async def delete_item(self, path_id: uuid.UUID, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.get_owned(path_id, user_id)
        item = await self.items.get(item_id)
        if item is None or item.path_id != path_id:
            raise NotFoundError("Learning path item", item_id)
        await self.items.delete(item)
        await self._recalculate_total(path_id)
        await self.commit()

    async def _reload_item(self, item_id: uuid.UUID) -> LearningPathItem:
        """Re-read with relationships eagerly loaded, ready to serialise."""
        item = await self.items.get(item_id)
        if item is None:
            raise NotFoundError("Learning path item", item_id)
        return item

    async def _recalculate_total(self, path_id: uuid.UUID) -> None:
        path = await self.paths.get(path_id)
        if path is not None:
            path.total_estimated_minutes = await self.items.total_minutes(path_id)
            await self.session.flush()

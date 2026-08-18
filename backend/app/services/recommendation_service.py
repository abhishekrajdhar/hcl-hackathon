"""Recommendation persistence and lifecycle.

Scoring and ranking are NOT implemented here — that engine is a later phase.
This service stores, serves and transitions recommendations that something
else produced.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.enums import RecommendationStatus
from app.models.recommendation import Recommendation
from app.repositories.path import LearningPathRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.resource import ResourceRepository
from app.repositories.skill import SkillRepository
from app.schemas.recommendation import RecommendationCreate
from app.services.base import BaseService


class RecommendationService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.recommendations = RecommendationRepository(session)
        self.resources = ResourceRepository(session)
        self.skills = SkillRepository(session)
        self.paths = LearningPathRepository(session)

    async def get_owned(self, recommendation_id: uuid.UUID, user_id: uuid.UUID) -> Recommendation:
        entry = await self.recommendations.get(recommendation_id)
        if entry is None or entry.user_id != user_id:
            raise NotFoundError("Recommendation", recommendation_id)
        return entry

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
        status: RecommendationStatus | None = None,
    ) -> tuple[list[Recommendation], int]:
        filters = [Recommendation.user_id == user_id]
        if status:
            filters.append(Recommendation.status == status)
        items = await self.recommendations.list(
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=(Recommendation.rank, Recommendation.score.desc()),
        )
        total = await self.recommendations.count(filters)
        return items, total

    async def create_for_user(
        self, user_id: uuid.UUID, payload: RecommendationCreate
    ) -> Recommendation:
        if await self.resources.get(payload.resource_id) is None:
            raise NotFoundError("Resource", payload.resource_id)
        if payload.skill_id is not None and await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)
        if payload.path_id is not None:
            path = await self.paths.get(payload.path_id)
            if path is None or path.user_id != user_id:
                raise NotFoundError("Learning path", payload.path_id)

        created = await self.recommendations.create(
            {**payload.model_dump(), "user_id": user_id}
        )
        await self.commit()
        return await self.get_owned(created.id, user_id)

    async def set_status(
        self, recommendation_id: uuid.UUID, user_id: uuid.UUID, status: RecommendationStatus
    ) -> Recommendation:
        entry = await self.get_owned(recommendation_id, user_id)
        await self.recommendations.update(
            entry, {"status": status, "responded_at": datetime.now(timezone.utc)}
        )
        await self.commit()
        return await self.get_owned(recommendation_id, user_id)

    async def delete(self, recommendation_id: uuid.UUID, user_id: uuid.UUID) -> None:
        entry = await self.get_owned(recommendation_id, user_id)
        await self.recommendations.delete(entry)
        await self.commit()

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.enums import FeedbackTargetType
from app.models.feedback import Feedback
from app.repositories.assessment import AssessmentRepository
from app.repositories.feedback import FeedbackRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.resource import ResourceRepository
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate
from app.services.base import BaseService


class FeedbackService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.feedback = FeedbackRepository(session)
        self._targets = {
            FeedbackTargetType.RESOURCE: ResourceRepository(session),
            FeedbackTargetType.PATH: LearningPathRepository(session),
            FeedbackTargetType.PATH_ITEM: LearningPathItemRepository(session),
            FeedbackTargetType.RECOMMENDATION: RecommendationRepository(session),
            FeedbackTargetType.ASSESSMENT: AssessmentRepository(session),
        }

    async def _assert_target_exists(
        self, target_type: FeedbackTargetType, target_id: uuid.UUID
    ) -> None:
        repo = self._targets[target_type]
        if await repo.get(target_id) is None:
            raise NotFoundError(target_type.value.replace("_", " ").title(), target_id)

    async def create(self, user_id: uuid.UUID, payload: FeedbackCreate) -> Feedback:
        await self._assert_target_exists(payload.target_type, payload.target_id)
        entry = await self.feedback.create({**payload.model_dump(), "user_id": user_id})
        await self.commit()
        return entry

    async def get_owned(self, feedback_id: uuid.UUID, user_id: uuid.UUID) -> Feedback:
        entry = await self.feedback.get(feedback_id)
        if entry is None or entry.user_id != user_id:
            raise NotFoundError("Feedback", feedback_id)
        return entry

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Feedback], int]:
        filters = [Feedback.user_id == user_id]
        items = await self.feedback.list(
            limit=limit, offset=offset, filters=filters, order_by=(Feedback.created_at.desc(),)
        )
        total = await self.feedback.count(filters)
        return items, total

    async def update(
        self, feedback_id: uuid.UUID, user_id: uuid.UUID, payload: FeedbackUpdate
    ) -> Feedback:
        entry = await self.get_owned(feedback_id, user_id)
        await self.feedback.update(entry, payload.model_dump(exclude_unset=True))
        await self.commit()
        return entry

    async def delete(self, feedback_id: uuid.UUID, user_id: uuid.UUID) -> None:
        entry = await self.get_owned(feedback_id, user_id)
        await self.feedback.delete(entry)
        await self.commit()

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.enums import FeedbackTargetType
from app.models.feedback import Feedback
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    model = Feedback

    async def list_for_target(
        self, target_type: FeedbackTargetType, target_id: uuid.UUID
    ) -> list[Feedback]:
        stmt = (
            select(Feedback)
            .where(Feedback.target_type == target_type, Feedback.target_id == target_id)
            .order_by(Feedback.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

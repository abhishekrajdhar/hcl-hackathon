from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.models.enums import RecommendationStatus
from app.models.recommendation import Recommendation
from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.models.skill import Skill
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[Recommendation]):
    model = Recommendation

    def _base_select(self) -> Select[tuple[Recommendation]]:
        return select(Recommendation).options(
            selectinload(Recommendation.resource)
            .selectinload(Resource.skills)
            .selectinload(ResourceSkill.skill)
            .selectinload(Skill.category),
            selectinload(Recommendation.resource)
            .selectinload(Resource.prerequisites)
            .selectinload(ResourcePrerequisite.skill)
            .selectinload(Skill.category),
        )

    async def list_pending_for_user(
        self, user_id: uuid.UUID, *, limit: int = 20
    ) -> list[Recommendation]:
        stmt = (
            self._base_select()
            .where(
                Recommendation.user_id == user_id,
                Recommendation.status == RecommendationStatus.PENDING,
            )
            .order_by(Recommendation.rank, Recommendation.score.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

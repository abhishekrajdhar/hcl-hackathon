from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.goal import LearningGoal, LearningGoalSkill
from app.models.skill import Skill
from app.repositories.base import BaseRepository


class LearningGoalRepository(BaseRepository[LearningGoal]):
    model = LearningGoal

    def _base_select(self) -> Select[tuple[LearningGoal]]:
        return select(LearningGoal).options(
            selectinload(LearningGoal.target_skills)
            .joinedload(LearningGoalSkill.skill)
            .joinedload(Skill.category)
        )


class LearningGoalSkillRepository(BaseRepository[LearningGoalSkill]):
    model = LearningGoalSkill

    def _base_select(self) -> Select[tuple[LearningGoalSkill]]:
        return select(LearningGoalSkill).options(
            joinedload(LearningGoalSkill.skill).joinedload(Skill.category)
        )

    async def get_entry(self, goal_id: uuid.UUID, skill_id: uuid.UUID) -> LearningGoalSkill | None:
        stmt = self._base_select().where(
            LearningGoalSkill.goal_id == goal_id, LearningGoalSkill.skill_id == skill_id
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

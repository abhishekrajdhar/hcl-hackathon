from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.goal import LearningGoal, LearningGoalSkill
from app.repositories.goal import LearningGoalRepository, LearningGoalSkillRepository
from app.repositories.skill import SkillRepository
from app.schemas.goal import (
    GoalSkillCreate,
    GoalSkillUpdate,
    LearningGoalCreate,
    LearningGoalUpdate,
)
from app.services.base import BaseService


class GoalService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.goals = LearningGoalRepository(session)
        self.goal_skills = LearningGoalSkillRepository(session)
        self.skills = SkillRepository(session)

    async def get_owned(self, goal_id: uuid.UUID, user_id: uuid.UUID) -> LearningGoal:
        goal = await self.goals.get(goal_id)
        if goal is None:
            raise NotFoundError("Learning goal", goal_id)
        if goal.user_id != user_id:
            # 404 rather than 403: do not confirm the row exists to a non-owner.
            raise NotFoundError("Learning goal", goal_id)
        return goal

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int, status: str | None = None
    ) -> tuple[list[LearningGoal], int]:
        filters = [LearningGoal.user_id == user_id]
        if status:
            filters.append(LearningGoal.status == status)
        items = await self.goals.list(
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=(LearningGoal.priority, LearningGoal.created_at.desc()),
        )
        total = await self.goals.count(filters)
        return items, total

    async def create(self, user_id: uuid.UUID, payload: LearningGoalCreate) -> LearningGoal:
        data = payload.model_dump(exclude={"target_skills"})
        goal = await self.goals.create({**data, "user_id": user_id})

        for entry in payload.target_skills:
            if await self.skills.get(entry.skill_id) is None:
                raise NotFoundError("Skill", entry.skill_id)
            self.goal_skills.add(
                LearningGoalSkill(goal_id=goal.id, **entry.model_dump())
            )
        await self.session.flush()
        await self.commit()
        refreshed = await self.goals.get(goal.id)
        assert refreshed is not None
        return refreshed

    async def update(
        self, goal_id: uuid.UUID, user_id: uuid.UUID, payload: LearningGoalUpdate
    ) -> LearningGoal:
        goal = await self.get_owned(goal_id, user_id)
        await self.goals.update(goal, payload.model_dump(exclude_unset=True))
        await self.commit()
        return goal

    async def delete(self, goal_id: uuid.UUID, user_id: uuid.UUID) -> None:
        goal = await self.get_owned(goal_id, user_id)
        await self.goals.delete(goal)
        await self.commit()

    # --- target skill vector ---------------------------------------------
    async def add_target_skill(
        self, goal_id: uuid.UUID, user_id: uuid.UUID, payload: GoalSkillCreate
    ) -> LearningGoalSkill:
        await self.get_owned(goal_id, user_id)
        if await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)
        if await self.goal_skills.get_entry(goal_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already a target of the goal", error_code="goal_skill_exists"
            )
        await self.goal_skills.create({**payload.model_dump(), "goal_id": goal_id})
        await self.commit()
        entry = await self.goal_skills.get_entry(goal_id, payload.skill_id)
        assert entry is not None
        return entry

    async def update_target_skill(
        self,
        goal_id: uuid.UUID,
        skill_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: GoalSkillUpdate,
    ) -> LearningGoalSkill:
        await self.get_owned(goal_id, user_id)
        entry = await self.goal_skills.get_entry(goal_id, skill_id)
        if entry is None:
            raise NotFoundError("Goal target skill", skill_id)
        await self.goal_skills.update(entry, payload.model_dump(exclude_unset=True))
        await self.commit()
        return entry

    async def remove_target_skill(
        self, goal_id: uuid.UUID, skill_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self.get_owned(goal_id, user_id)
        entry = await self.goal_skills.get_entry(goal_id, skill_id)
        if entry is None:
            raise NotFoundError("Goal target skill", skill_id)
        await self.goal_skills.delete(entry)
        await self.commit()

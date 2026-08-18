from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.skill import UserSkill
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.schemas.skill import UserSkillCreate, UserSkillUpdate
from app.services.base import BaseService


class UserSkillService(BaseService):
    """The learner's mastery vector."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.user_skills = UserSkillRepository(session)
        self.skills = SkillRepository(session)

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[UserSkill], int]:
        filters = [UserSkill.user_id == user_id]
        items = await self.user_skills.list(
            limit=limit, offset=offset, filters=filters, order_by=(UserSkill.created_at.desc(),)
        )
        total = await self.user_skills.count(filters)
        return items, total

    async def get(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> UserSkill:
        entry = await self.user_skills.get_for_user(user_id, skill_id)
        if entry is None:
            raise NotFoundError("Skill entry for this user", skill_id)
        return entry

    async def add(self, user_id: uuid.UUID, payload: UserSkillCreate) -> UserSkill:
        if await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)
        if await self.user_skills.get_for_user(user_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already on the learner's profile", error_code="user_skill_exists"
            )
        await self.user_skills.create({**payload.model_dump(), "user_id": user_id})
        await self.commit()
        # Re-read so the nested skill relationship is loaded for serialisation.
        return await self.get(user_id, payload.skill_id)

    async def upsert(self, user_id: uuid.UUID, payload: UserSkillCreate) -> UserSkill:
        if await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)
        existing = await self.user_skills.get_for_user(user_id, payload.skill_id)
        if existing is None:
            return await self.add(user_id, payload)
        await self.user_skills.update(
            existing, payload.model_dump(exclude={"skill_id"}, exclude_unset=True)
        )
        await self.commit()
        return existing

    async def update(
        self, user_id: uuid.UUID, skill_id: uuid.UUID, payload: UserSkillUpdate
    ) -> UserSkill:
        entry = await self.get(user_id, skill_id)
        await self.user_skills.update(entry, payload.model_dump(exclude_unset=True))
        await self.commit()
        return entry

    async def delete(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        entry = await self.get(user_id, skill_id)
        await self.user_skills.delete(entry)
        await self.commit()

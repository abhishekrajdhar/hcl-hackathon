from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.user import LearnerProfile
from app.repositories.user import LearnerProfileRepository
from app.schemas.profile import LearnerProfileCreate, LearnerProfileUpdate
from app.services.base import BaseService


class ProfileService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.profiles = LearnerProfileRepository(session)

    async def get_for_user(self, user_id: uuid.UUID) -> LearnerProfile:
        profile = await self.profiles.get_by_user(user_id)
        if profile is None:
            raise NotFoundError("Learner profile for this user")
        return profile

    async def create_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileCreate
    ) -> LearnerProfile:
        if await self.profiles.get_by_user(user_id) is not None:
            raise ConflictError(
                "This user already has a profile; update it instead",
                error_code="profile_exists",
            )
        profile = await self.profiles.create({**payload.model_dump(), "user_id": user_id})
        await self.commit()
        return profile

    async def update_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileUpdate
    ) -> LearnerProfile:
        profile = await self.get_for_user(user_id)
        data = payload.model_dump(exclude_unset=True)
        if data:
            # Every accepted edit advances the profile version so downstream
            # snapshots can tell which revision they were computed from.
            data["version"] = profile.version + 1
            await self.profiles.update(profile, data)
            await self.commit()
        return profile

    async def upsert_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileCreate
    ) -> LearnerProfile:
        existing = await self.profiles.get_by_user(user_id)
        if existing is None:
            return await self.create_for_user(user_id, payload)
        await self.profiles.update(
            existing, {**payload.model_dump(), "version": existing.version + 1}
        )
        await self.commit()
        return existing

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile = await self.get_for_user(user_id)
        await self.profiles.delete(profile)
        await self.commit()

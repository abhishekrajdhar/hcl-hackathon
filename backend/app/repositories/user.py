from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.user import LearnerProfile, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self.session.execute(stmt)).scalars().one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(func.lower(User.email) == email.lower()).limit(1)
        return (await self.session.execute(stmt)).first() is not None


class LearnerProfileRepository(BaseRepository[LearnerProfile]):
    model = LearnerProfile

    async def get_by_user(self, user_id: uuid.UUID) -> LearnerProfile | None:
        return await self.get_by(user_id=user_id)

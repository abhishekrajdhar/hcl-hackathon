from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.base import BaseService


class UserService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.users = UserRepository(session)

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    async def list(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        items = await self.users.list(limit=limit, offset=offset, order_by=(User.created_at.desc(),))
        total = await self.users.count()
        return items, total

    async def create(self, payload: UserCreate) -> User:
        if await self.users.email_exists(payload.email):
            raise ConflictError(
                "An account with this email already exists", error_code="email_taken"
            )
        user = await self.users.create(
            {
                "email": payload.email.lower(),
                "hashed_password": hash_password(payload.password),
                "full_name": payload.full_name,
                "timezone": payload.timezone,
                "role": payload.role,
            }
        )
        await self.commit()
        return user

    async def update(self, user_id: uuid.UUID, payload: UserUpdate) -> User:
        user = await self.get(user_id)
        data = payload.model_dump(exclude_unset=True)
        if "password" in data:
            password = data.pop("password")
            if password is not None:
                data["hashed_password"] = hash_password(password)
        await self.users.update(user, data)
        await self.commit()
        return user

    async def delete(self, user_id: uuid.UUID) -> None:
        user = await self.get(user_id)
        await self.users.delete(user)
        await self.commit()

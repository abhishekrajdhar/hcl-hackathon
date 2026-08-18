from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.base import BaseService


class AuthService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
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
                "role": UserRole.LEARNER,
            }
        )
        await self.commit()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        # Same message for unknown email and bad password: do not leak which.
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password", error_code="invalid_credentials")
        if not user.is_active:
            raise ForbiddenError("This account is disabled", error_code="account_disabled")

        user.last_login_at = datetime.now(timezone.utc)
        await self.commit()
        return user

    @staticmethod
    def issue_token(user: User) -> tuple[str, int]:
        token = create_access_token(user.id, role=user.role.value)
        return token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.llm.base import LLMProvider
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False so a missing header raises our own 401 problem document
# rather than FastAPI's bare {"detail": ...} body.
_bearer = HTTPBearer(auto_error=False, description="JWT access token")


class Pagination:
    """Offset pagination shared by every list endpoint.

    Query() is used as a default rather than via Annotated because this module
    enables postponed annotations, which would stringify Annotated metadata.
    """

    def __init__(
        self,
        limit: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Authentication credentials were not provided")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Malformed token subject", error_code="invalid_token") from exc

    user = await UserRepository(session).get(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists", error_code="invalid_token")
    if not user.is_active:
        raise ForbiddenError("This account is disabled", error_code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("This operation requires administrator privileges")
    return user


AdminUser = Annotated[User, Depends(get_current_admin)]


def get_llm_provider_dep() -> LLMProvider:
    """The configured LLM provider (settings-driven, cached).

    Wrapped in a dependency so tests can override it with a seeded MockProvider
    via FastAPI dependency overrides — the provider is never hard-coded in a
    router.
    """
    from app.llm.factory import get_llm_provider

    return get_llm_provider()


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider_dep)]

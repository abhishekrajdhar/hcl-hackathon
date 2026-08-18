from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import AdminUser, CurrentUser, PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead], summary="List users (admin)")
async def list_users(session: SessionDep, pagination: PaginationDep, _: AdminUser) -> Page[UserRead]:
    items, total = await UserService(session).list(
        limit=pagination.limit, offset=pagination.offset
    )
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, _: AdminUser) -> UserRead:
    user = await UserService(session).create(payload)
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate, session: SessionDep, current_user: CurrentUser
) -> UserRead:
    # A learner may not flip their own `is_active` flag.
    safe = payload.model_copy(update={"is_active": None})
    user = await UserService(session).update(current_user.id, safe)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, session: SessionDep, _: AdminUser) -> UserRead:
    return UserRead.model_validate(await UserService(session).get(user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, session: SessionDep, _: AdminUser
) -> UserRead:
    return UserRead.model_validate(await UserService(session).update(user_id, payload))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_user(user_id: uuid.UUID, session: SessionDep, _: AdminUser) -> None:
    await UserService(session).delete(user_id)

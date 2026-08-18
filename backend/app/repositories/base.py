"""Generic async data-access layer.

Repositories own *how* data is fetched and persisted; they contain no business
rules and never raise HTTP errors. They flush but do not commit — transaction
boundaries belong to the service layer.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import strategy_options

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- read ------------------------------------------------------------
    def _base_select(self) -> Select[tuple[ModelT]]:
        return select(self.model)

    async def get(
        self,
        entity_id: uuid.UUID,
        *,
        options: Sequence[strategy_options._AbstractLoad] | None = None,
    ) -> ModelT | None:
        stmt = self._base_select().where(self.model.id == entity_id)
        if options:
            stmt = stmt.options(*options)
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = self._base_select().filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        filters: Sequence[Any] = (),
        order_by: Sequence[Any] = (),
        options: Sequence[strategy_options._AbstractLoad] | None = None,
    ) -> list[ModelT]:
        stmt = self._base_select()
        if filters:
            stmt = stmt.where(*filters)
        if options:
            stmt = stmt.options(*options)
        stmt = stmt.order_by(*(order_by or (self.model.id,))).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def count(self, filters: Sequence[Any] = ()) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        return int((await self.session.execute(stmt)).scalar_one())

    async def exists(self, filters: Sequence[Any] = ()) -> bool:
        stmt = select(self.model.id)
        if filters:
            stmt = stmt.where(*filters)
        return (await self.session.execute(stmt.limit(1))).first() is not None

    # --- write -----------------------------------------------------------
    async def create(self, data: dict[str, Any]) -> ModelT:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    async def update(self, instance: ModelT, data: dict[str, Any]) -> ModelT:
        for field, value in data.items():
            setattr(instance, field, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def delete_where(self, filters: Sequence[Any]) -> int:
        result = await self.session.execute(delete(self.model).where(*filters))
        await self.session.flush()
        return int(result.rowcount or 0)

    async def refresh(self, instance: ModelT) -> ModelT:
        await self.session.refresh(instance)
        return instance

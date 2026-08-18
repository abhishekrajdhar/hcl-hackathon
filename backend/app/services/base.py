"""Service-layer helpers.

Services own the transaction boundary, enforce business rules and raise the
domain exceptions from `app.core.errors`. Routers must not do any of that.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import Page

T = TypeVar("T")


class BaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()


def build_page(items: Sequence[Any], total: int, limit: int, offset: int) -> Page[Any]:
    return Page(items=list(items), total=total, limit=limit, offset=offset)

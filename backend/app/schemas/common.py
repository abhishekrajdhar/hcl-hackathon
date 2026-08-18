"""Shared schema primitives: ORM base, pagination, error envelope."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for every response schema read out of the ORM."""

    model_config = ConfigDict(from_attributes=True)


class IdentifiedModel(ORMModel):
    id: uuid.UUID


class TimestampedModel(IdentifiedModel):
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    """Offset-paginated envelope."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class Message(BaseModel):
    message: str


class ProblemDetail(BaseModel):
    """RFC 7807 error body. Documented so it shows up in the OpenAPI spec."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    extra: dict | None = None

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import TimestampedModel


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.LEARNER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    is_active: bool | None = None


class UserRead(TimestampedModel):
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    timezone: str
    last_login_at: datetime | None

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FeedbackSignal, FeedbackTargetType
from app.schemas.common import TimestampedModel


class FeedbackCreate(BaseModel):
    target_type: FeedbackTargetType
    target_id: uuid.UUID
    signal: FeedbackSignal
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=4000)


class FeedbackUpdate(BaseModel):
    signal: FeedbackSignal | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=4000)


class FeedbackRead(TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    target_type: FeedbackTargetType
    target_id: uuid.UUID
    signal: FeedbackSignal
    rating: int | None
    comment: str | None

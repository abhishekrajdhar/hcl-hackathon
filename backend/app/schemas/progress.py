from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProgressEventType
from app.schemas.common import TimestampedModel


class ProgressEventCreate(BaseModel):
    path_item_id: uuid.UUID | None = None
    resource_id: uuid.UUID | None = None
    event_type: ProgressEventType
    progress_pct: float = Field(default=0.0, ge=0, le=100)
    time_spent_minutes: int = Field(default=0, ge=0)
    occurred_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProgressEventRead(TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    path_item_id: uuid.UUID | None
    resource_id: uuid.UUID | None
    event_type: ProgressEventType
    progress_pct: float
    time_spent_minutes: int
    occurred_at: datetime
    details: dict[str, Any]


class ProgressSummary(BaseModel):
    """Derived view over the event log — no state is stored for this."""

    user_id: uuid.UUID
    total_events: int
    items_started: int
    items_completed: int
    total_time_minutes: int
    active_path_id: uuid.UUID | None = None
    active_path_total_items: int = 0
    active_path_completed_items: int = 0
    completion_pct: float = 0.0
    last_activity_at: datetime | None = None

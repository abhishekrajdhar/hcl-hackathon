"""Schemas for the conversational learning assistant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ToolInvocation(BaseModel):
    name: str
    available: bool
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    intent: str
    #: Which application tools were consulted (transparency; these are the only
    #: source of any application facts in the reply).
    tools_used: list[ToolInvocation] = Field(default_factory=list)
    source: Literal["llm", "template"]


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)

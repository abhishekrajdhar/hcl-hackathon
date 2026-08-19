"""Conversational learning-assistant endpoints.

The assistant reads and writes application state only through tools that call the
real services; it never fabricates state. Control flow (intent detection, tool
selection) is deterministic; the LLM only phrases the final reply from tool data.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import (
    CurrentUser,
    EmbeddingProviderDep,
    LLMProviderDep,
    PaginationDep,
    SessionDep,
)
from app.core.errors import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationRead,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the personalized learning coach",
)
async def chat(
    payload: ChatRequest,
    session: SessionDep,
    provider: LLMProviderDep,
    embeddings: EmbeddingProviderDep,
    current_user: CurrentUser,
) -> ChatResponse:
    return await ChatService(session, provider, embeddings).chat(
        current_user.id, payload.message, payload.conversation_id
    )


@router.get(
    "/conversations",
    response_model=list[ConversationRead],
    summary="List the learner's conversations",
)
async def list_conversations(
    session: SessionDep, pagination: PaginationDep, current_user: CurrentUser
) -> list[ConversationRead]:
    convos = await ConversationRepository(session).list_for_user(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    return [ConversationRead.model_validate(c) for c in convos]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Full conversation history (dialogue only — no application state)",
)
async def get_conversation(
    conversation_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> ConversationDetail:
    convo = await ConversationRepository(session).get_with_messages(conversation_id)
    if convo is None:
        raise NotFoundError("Conversation", conversation_id)
    if convo.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You may only view your own conversations")
    detail = ConversationDetail.model_validate(convo)
    return detail.model_copy(
        update={"messages": [ChatMessageRead.model_validate(m) for m in convo.messages]}
    )

"""Conversational learning assistant — the Conversation Manager.

Pipeline (deterministic control flow, no hallucinated state):

    message -> detect intent -> select tools -> run tools (application services)
            -> compose grounded reply -> (optional LLM rephrase, grounded)
            -> persist the turn

Application state and conversation memory are kept strictly separate: the
messages table stores only the dialogue, while every application fact is fetched
fresh through a tool each turn. The assistant never invents skills, scores,
completed courses, recommendations or milestones — if a tool has no data, it
says so.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.embeddings.base import EmbeddingProvider
from app.engines.chat import IntentKind, compose_reply, detect_intent
from app.engines.chat.intent import Intent
from app.engines.explanation import check_grounding
from app.llm.base import LLMError, LLMProvider
from app.models.conversation import Conversation, ConversationMessage
from app.models.enums import ChatRole
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import ChatResponse, ToolInvocation
from app.schemas.profile import LearnerProfileUpdate
from app.services.base import BaseService
from app.services.chat_tools import TOOL_DESCRIPTIONS, ChatToolExecutor, ToolResult
from app.services.profile_service import ProfileService

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a personalized learning coach for a single learner. You are warm, "
    "concise and encouraging. You help the learner reach their career goal step "
    "by step.\n"
    "CRITICAL: You may ONLY state facts contained in the tool results provided to "
    "you. Never invent skill levels, assessment scores, completed courses, "
    "recommendations, or roadmap milestones. If the tool results do not contain "
    "the answer, say you don't have that information yet and suggest how to get "
    "it. Rephrase the provided draft in your own warm voice, but do not add facts.\n"
    "Available tools (already run for you): "
    + "; ".join(f"{k}: {v}" for k, v in TOOL_DESCRIPTIONS.items())
)


class ChatService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        super().__init__(session)
        self.llm = llm_provider
        self.embeddings = embedding_provider
        self.conversations = ConversationRepository(session)

    async def chat(
        self, user_id: uuid.UUID, message: str, conversation_id: uuid.UUID | None = None
    ) -> ChatResponse:
        conversation = await self._resolve_conversation(user_id, conversation_id, message)

        # store the user turn
        self.session.add(
            ConversationMessage(conversation_id=conversation.id, role=ChatRole.USER, content=message)
        )
        await self.session.flush()

        intent = detect_intent(message)
        # side-effecting intents (writes) are handled explicitly, not by the LLM
        if intent.kind == IntentKind.SET_GOAL and intent.goal_text:
            await self._set_goal(user_id, intent.goal_text)

        results = await self._run_tools(user_id, intent)
        draft = compose_reply(intent, results)
        reply, source = await self._maybe_rephrase(message, draft, results)

        self.session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role=ChatRole.ASSISTANT,
                content=reply,
                meta={
                    "intent": intent.kind.value,
                    "tools_used": [r.name for r in results],
                    "source": source,
                },
            )
        )
        await self.session.flush()
        await self.commit()

        return ChatResponse(
            conversation_id=conversation.id,
            reply=reply,
            intent=intent.kind.value,
            tools_used=[
                ToolInvocation(name=r.name, available=r.available, summary=r.summary, data=r.data)
                for r in results
            ],
            source=source,
        )

    # --- conversation memory (separate from app state) -------------------
    async def _resolve_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID | None, message: str
    ) -> Conversation:
        if conversation_id is not None:
            conversation = await self.conversations.get(conversation_id)
            if conversation is None:
                raise NotFoundError("Conversation", conversation_id)
            if conversation.user_id != user_id:
                raise ForbiddenError("You may only continue your own conversations")
            return conversation
        conversation = Conversation(user_id=user_id, title=message[:60])
        self.conversations.add(conversation)
        await self.session.flush()
        return conversation

    # --- tool selection + execution --------------------------------------
    async def _run_tools(self, user_id: uuid.UUID, intent: Intent) -> list[ToolResult]:
        tools = ChatToolExecutor(self.session, user_id, self.embeddings) if self.embeddings else None
        selected = _TOOL_PLAN.get(intent.kind, [])
        results: list[ToolResult] = []
        for name in selected:
            if tools is None and name == "search_resources":
                continue
            executor = ChatToolExecutor(self.session, user_id, self.embeddings)  # type: ignore[arg-type]
            if name == "search_resources":
                results.append(await executor.search_resources(intent.query or intent.raw))
            elif name == "update_learning_progress":
                results.append(
                    await executor.update_learning_progress(
                        resource_ref=intent.resource_ref, score=intent.score
                    )
                )
            else:
                results.append(await getattr(executor, name)())
        return results

    async def _set_goal(self, user_id: uuid.UUID, goal_text: str) -> None:
        service = ProfileService(self.session)
        try:
            await service.update_for_user(
                user_id, LearnerProfileUpdate(target_role=goal_text, goal_text_raw=goal_text)
            )
        except NotFoundError:
            from app.schemas.profile import LearnerProfileCreate

            await service.create_for_user(
                user_id, LearnerProfileCreate(target_role=goal_text, goal_text_raw=goal_text)
            )

    # --- optional LLM rephrase (grounded) --------------------------------
    async def _maybe_rephrase(
        self, message: str, draft: str, results: list[ToolResult]
    ) -> tuple[str, str]:
        if self.llm is None:
            return draft, "template"
        try:
            completion = await self.llm.complete(
                system=SYSTEM_PROMPT,
                user=(
                    f"Learner said: {message}\n\n"
                    f"Tool results (the only facts you may use):\n"
                    f"{json.dumps([{'tool': r.name, 'available': r.available, 'data': r.data} for r in results], default=str)[:4000]}\n\n"
                    f"Draft reply to rephrase warmly (do not add facts):\n{draft}"
                ),
                max_tokens=400,
            )
            text = completion.text.strip()
        except LLMError as exc:
            logger.warning("chat LLM failed; using template", extra={"error": str(exc)[:200]})
            return draft, "template"

        # Reject anything that is not plain prose (e.g. a model that returned
        # structured JSON): a chat reply must read as coaching, not data.
        if not text or text.lstrip()[:1] in "{[" or '":' in text:
            return draft, "template"

        levels, terms = _grounding_allowances(results, draft)
        if check_grounding(text, allowed_levels=levels, allowed_terms=terms).grounded:
            return text, "llm"
        logger.warning("chat reply failed grounding; using template")
        return draft, "template"


#: Which tools each intent needs. This is deterministic tool SELECTION — the LLM
#: never chooses what application data to read.
_TOOL_PLAN: dict[IntentKind, list[str]] = {
    IntentKind.GREETING: ["get_learner_profile"],
    IntentKind.SET_GOAL: ["get_learner_profile"],
    IntentKind.NEXT_ACTION: ["get_next_action"],
    IntentKind.WEEKLY_PLAN: ["get_current_learning_path", "get_progress"],
    IntentKind.EXPLAIN_RECOMMENDATION: ["get_recommendations"],
    IntentKind.CAN_I_SKIP: ["get_skill_gaps", "get_learner_profile"],
    IntentKind.SHOW_PATH: ["get_current_learning_path"],
    IntentKind.SHOW_GAPS: ["get_skill_gaps"],
    IntentKind.SHOW_RECOMMENDATIONS: ["get_recommendations"],
    IntentKind.SHOW_PROGRESS: ["get_progress"],
    IntentKind.SHOW_PROFILE: ["get_learner_profile"],
    IntentKind.SEARCH_RESOURCES: ["search_resources"],
    IntentKind.REPORT_SCORE: ["update_learning_progress"],
    IntentKind.REPORT_COMPLETION: ["update_learning_progress"],
    IntentKind.UNKNOWN: [],
}


def _grounding_allowances(results: list[ToolResult], draft: str) -> tuple[list[float], list[str]]:
    """Numbers and names the LLM is allowed to mention (from tool data + draft)."""
    levels: list[float] = []
    terms: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, float):
            levels.append(value)
        elif isinstance(value, str):
            terms.append(value)

    for r in results:
        walk(r.data)
        terms.append(r.summary)
    terms.append(draft)
    return levels, terms

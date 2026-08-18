"""Semantic resource retrieval.

Turns an intent (a raw query, a goal, a skill, a learner profile) into a
canonical query text, embeds it once, and asks pgvector for the nearest
resources by cosine distance. All ranking is vector arithmetic in the database —
never an LLM.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.text import (
    canonical_goal_query_text,
    canonical_profile_query_text,
    canonical_skill_query_text,
)
from app.models.resource import Resource
from app.repositories.goal import LearningGoalRepository
from app.repositories.resource import ResourceRepository
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.repositories.user import LearnerProfileRepository
from app.services.base import BaseService
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True, slots=True)
class ScoredResource:
    resource: Resource
    similarity: float
    distance: float


class SemanticSearchService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider,
        cache: EmbeddingCache | None = None,
    ) -> None:
        super().__init__(session)
        self.provider = provider
        self.embeddings = EmbeddingService(session, provider, cache)
        self.resources = ResourceRepository(session)
        self.skills = SkillRepository(session)
        self.user_skills = UserSkillRepository(session)
        self.goals = LearningGoalRepository(session)
        self.profiles = LearnerProfileRepository(session)

    # --- core search -----------------------------------------------------
    async def semantic_search(
        self,
        query: str,
        *,
        top_k: int = 10,
        resource_type: Any = None,
        max_difficulty: int | None = None,
        skill_id: uuid.UUID | None = None,
    ) -> list[ScoredResource]:
        cleaned = " ".join(query.split())
        if not cleaned:
            raise ValidationError("Query text is empty", error_code="empty_query")

        embedding = await self.embeddings.embed_query(cleaned)

        filters: list[Any] = [Resource.is_active.is_(True)]
        if resource_type is not None:
            filters.append(Resource.resource_type == resource_type)
        if max_difficulty is not None:
            filters.append(Resource.difficulty <= max_difficulty)
        if skill_id is not None:
            filters.append(ResourceRepository.teaches_skill_filter(skill_id))

        matches = await self.resources.semantic_search(embedding, top_k=top_k, filters=filters)
        return [self._score(resource, distance) for resource, distance in matches]

    @staticmethod
    def _score(resource: Resource, distance: float) -> ScoredResource:
        similarity = round(1.0 - distance, 6)
        return ScoredResource(resource=resource, similarity=similarity, distance=round(distance, 6))

    # --- search_resources_for_goal --------------------------------------
    async def search_resources_for_goal(
        self,
        *,
        goal_id: uuid.UUID | None = None,
        goal_text: str | None = None,
        user_id: uuid.UUID | None = None,
        top_k: int = 10,
    ) -> list[ScoredResource]:
        """Resources most relevant to a goal.

        Accepts an explicit goal row (built from its title, role and target
        skills) or free-text goal wording.
        """
        if goal_id is not None:
            goal = await self.goals.get(goal_id)
            if goal is None or (user_id is not None and goal.user_id != user_id):
                raise NotFoundError("Learning goal", goal_id)
            query = canonical_goal_query_text(
                title=goal.title,
                description=goal.description,
                target_role=goal.target_role,
                target_skill_names=[
                    ts.skill.name for ts in goal.target_skills if ts.skill is not None
                ],
            )
        elif goal_text:
            query = canonical_goal_query_text(title=goal_text)
        else:
            raise ValidationError(
                "Provide either goal_id or goal_text", error_code="goal_query_required"
            )
        return await self.semantic_search(query, top_k=top_k)

    # --- search_resources_for_skill -------------------------------------
    async def search_resources_for_skill(
        self, skill_id: uuid.UUID, *, top_k: int = 10, teaches_only: bool = False
    ) -> list[ScoredResource]:
        """Resources most relevant to developing one skill.

        Ranks semantically by the skill's own text; `teaches_only` additionally
        restricts to resources structurally linked as teaching the skill.
        """
        skill = await self.skills.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        query = canonical_skill_query_text(
            name=skill.name, description=skill.description, aliases=skill.aliases
        )
        return await self.semantic_search(
            query, top_k=top_k, skill_id=skill_id if teaches_only else None
        )

    # --- search_resources_for_profile -----------------------------------
    async def search_resources_for_profile(
        self, user_id: uuid.UUID, *, top_k: int = 10
    ) -> list[ScoredResource]:
        """Resources most relevant to a learner's overall intent.

        Built from the learner's goal wording, target role and interests, plus
        the skills they are actively working on.
        """
        profile = await self.profiles.get_by_user(user_id)
        if profile is None:
            raise NotFoundError("Learner profile for this user")

        from app.models.skill import UserSkill

        focus = await self.user_skills.list(
            limit=10,
            filters=[UserSkill.user_id == user_id],
            order_by=(UserSkill.proficiency.asc(),),  # weakest first = most to learn
        )
        query = canonical_profile_query_text(
            goal_text=profile.goal_text_raw,
            target_role=profile.target_role,
            interests=profile.interests,
            focus_skill_names=[us.skill.name for us in focus if us.skill is not None],
        )
        if not query.strip():
            raise ValidationError(
                "Profile has no goal, role, interests or skills to search from",
                error_code="empty_profile_query",
            )
        return await self.semantic_search(query, top_k=top_k)

"""Hybrid learning-resource recommendation engine.

Composes the deterministic pieces built earlier — the skill-gap engine, semantic
retrieval over pgvector, and per-resource signals — into one ranked list. The
scoring formula lives in `app.engines.recommendation`; this service loads the
inputs, retrieves candidates, ranks them and explains the result.

Two guarantees the spec calls for:
- It never just returns the most popular courses: quality/rating carries only a
  small weight, and relevance + readiness dominate.
- Recommendations suit the learner's CURRENT stage: a resource whose
  prerequisites are unmet is marked not-ready and demoted below (or excluded
  from) everything the learner can actually start — so a high-similarity
  advanced course does not outrank an accessible foundational one.

No LLM and no model arithmetic anywhere in the ranking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.text import canonical_goal_query_text
from app.engines.recommendation import (
    CandidateResource,
    CatalogueEntry,
    DeclaredCourse,
    LearnerContext,
    RecommendationWeights,
    ResourcePrerequisite,
    ScoredResource,
    TaughtSkill,
    score_resource,
    top_factors,
)
from app.models.enums import (
    FeedbackSignal,
    FeedbackTargetType,
    RecommendationStatus,
)
from app.models.feedback import Feedback
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.engines.recommendation import build_suppressions, match_declared_courses
from app.repositories.feedback import FeedbackRepository
from app.repositories.progress import UserProgressRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.resource import ResourceRepository
from app.repositories.skill import SkillRepository
from app.repositories.user import LearnerProfileRepository
from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from app.schemas.resource import ResourceRead
from app.schemas.skill_gap import RequiredSkillInput, SkillGapAnalyzeRequest, SkillRef
from app.services.base import BaseService
from app.services.embedding_service import EmbeddingService
from app.services.skill_gap_service import SkillGapService

def _as_uuid(value: object) -> uuid.UUID | None:
    """Profile JSON is free-form; a malformed id must not break ranking."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


_FEEDBACK_VALUE = {
    FeedbackSignal.LOVED: 1.0,
    FeedbackSignal.UP: 1.0,
    FeedbackSignal.DOWN: 0.0,
    FeedbackSignal.IRRELEVANT: 0.0,
}
#: Candidate pool pulled from semantic recall before feature re-ranking.
_POOL_MULTIPLIER = 5
_MIN_POOL = 30
_MAX_POOL = 80
#: Default required proficiency for an ad-hoc "optional skill" target.
_OPTIONAL_SKILL_LEVEL = 0.7


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    scored: ScoredResource
    resource: Resource


class RecommendationEngineService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        cache: EmbeddingCache | None = None,
        weights: RecommendationWeights | None = None,
    ) -> None:
        super().__init__(session)
        self.provider = embedding_provider
        self.embeddings = EmbeddingService(session, embedding_provider, cache)
        self.gap_service = SkillGapService(session)
        self.resources = ResourceRepository(session)
        self.skills = SkillRepository(session)
        self.profiles = LearnerProfileRepository(session)
        self.progress = UserProgressRepository(session)
        self.feedback = FeedbackRepository(session)
        self.recommendations = RecommendationRepository(session)
        self.weights = weights or RecommendationWeights()

    # --- 1. recommend_resources -----------------------------------------
    async def recommend_resources(
        self,
        request: RecommendationRequest,
        *,
        requesting_user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> RecommendationResponse:
        gap_request = await self._to_gap_request(request)
        # SkillGapService.compute enforces self/admin ownership before loading
        # any of the target learner's skills.
        computed = await self.gap_service.compute(
            gap_request, requesting_user_id=requesting_user_id, is_admin=is_admin
        )
        learner_id = computed.user_id or request.user_id

        gaps = {g.skill_id: g.gap for g in computed.analysis.ranked_gaps}

        profile = await self.profiles.get_by_user(learner_id)
        learner = LearnerContext(
            proficiencies=computed.current,
            gaps=gaps,
            preferred_modalities=frozenset(profile.preferred_modalities) if profile else frozenset(),
            weekly_hours=profile.weekly_hours if profile else None,
        )

        candidates = await self._retrieve_candidates(request, computed, gaps)
        provider_success = await self._provider_success(learner_id)

        scored = [
            RankedCandidate(
                scored=score_resource(
                    self._to_candidate(resource, similarity, provider_success),
                    learner,
                    weights=self.weights,
                ),
                resource=resource,
            )
            for resource, similarity in candidates
        ]

        # Prior learning is applied AFTER scoring and before ranking, so the
        # excluded count is reported rather than silently shrinking the pool.
        suppressed = await self._already_learned(learner_id, [rc.resource for rc in scored])
        fresh = [rc for rc in scored if rc.resource.id not in suppressed]
        already_learned = len(scored) - len(fresh)

        ranked, excluded = self.rank_resources(
            fresh, top_k=request.top_k, include_unready=request.include_unready
        )
        items = [self._to_item(rc, rank=index + 1) for index, rc in enumerate(ranked)]

        if request.persist:
            await self._persist(learner_id, items)

        return RecommendationResponse(
            user_id=learner_id,
            goal_id=request.goal_id,
            count=len(items),
            excluded_unready=excluded,
            excluded_already_learned=already_learned,
            weights=self._weights_dict(),
            recommendations=items,
        )

    # --- 2. rank_resources ----------------------------------------------
    def rank_resources(
        self,
        candidates: list[RankedCandidate],
        *,
        top_k: int,
        include_unready: bool,
    ) -> tuple[list[RankedCandidate], int]:
        """Order by score, always placing ready resources ahead of unready ones.

        Ready-first is what stops a high-similarity but too-advanced resource
        from being recommended over one the learner can start now. Deterministic:
        ties break by resource id.
        """
        def sort_key(rc: RankedCandidate) -> tuple:
            return (-rc.scored.score, str(rc.resource.id))

        ready = sorted((c for c in candidates if c.scored.is_ready), key=sort_key)
        unready = sorted((c for c in candidates if not c.scored.is_ready), key=sort_key)

        if include_unready:
            return (ready + unready)[:top_k], 0
        return ready[:top_k], len(unready)

    # --- 3. explain_ranking_factors -------------------------------------
    def explain_ranking_factors(self, rc: RankedCandidate) -> str:
        """Deterministic, template-built reason — never model-generated."""
        scored, resource = rc.scored, rc.resource

        if not scored.is_ready:
            missing = self._skill_names(resource, scored.unmet_prerequisite_ids, prereq=True)
            names = ", ".join(missing) if missing else "some prerequisites"
            return f"Not ready yet — build {names} first before taking this."

        parts: list[str] = []
        matched = self._skill_names(resource, scored.matched_gap_skill_ids, prereq=False)
        parts.append(
            f"Targets your skill gap in {', '.join(matched)}."
            if matched
            else "Relevant to your goal."
        )
        if scored.features["prerequisite_match"] >= 1.0:
            parts.append("You meet all its prerequisites.")
        if scored.features["difficulty_match"] >= 0.8:
            parts.append("Its level suits your current stage.")
        pretty = ", ".join(name.replace("_", " ") for name, _ in top_factors(scored, limit=3))
        parts.append(f"Top factors: {pretty}.")
        return " ".join(parts)

    # --- request assembly ------------------------------------------------
    async def _to_gap_request(self, request: RecommendationRequest) -> SkillGapAnalyzeRequest:
        target_skills = list(request.target_skills)
        optional_id = await self._resolve_optional_skill(request)
        if optional_id is not None and not any(t.skill_id == optional_id for t in target_skills):
            target_skills.append(
                RequiredSkillInput(skill_id=optional_id, required_level=_OPTIONAL_SKILL_LEVEL)
            )
        if request.goal_id is None and not target_skills:
            raise ValidationError(
                "Provide a goal, target skills, or an optional skill", error_code="no_goal"
            )
        return SkillGapAnalyzeRequest(
            user_id=request.user_id, goal_id=request.goal_id, target_skills=target_skills
        )

    async def _resolve_optional_skill(
        self, request: RecommendationRequest
    ) -> uuid.UUID | None:
        if request.skill_id is not None:
            if await self.skills.get(request.skill_id) is None:
                raise NotFoundError("Skill", request.skill_id)
            return request.skill_id
        if request.skill_slug:
            skill = await self.skills.get_by_slug(request.skill_slug)
            if skill is None:
                raise NotFoundError("Skill", request.skill_slug)
            return skill.id
        return None

    # --- candidate retrieval (semantic recall) ---------------------------
    async def _retrieve_candidates(
        self, request: RecommendationRequest, computed, gaps: dict[uuid.UUID, float]
    ) -> list[tuple[Resource, float]]:
        query = self._build_query(request, computed, gaps)
        embedding = await self.embeddings.embed_query(query)

        filters = [Resource.is_active.is_(True)]
        optional_id = await self._resolve_optional_skill(request)
        if optional_id is not None:
            filters.append(ResourceRepository.teaches_skill_filter(optional_id))

        pool = max(_MIN_POOL, min(_MAX_POOL, request.top_k * _POOL_MULTIPLIER))
        matches = await self.resources.semantic_search(embedding, top_k=pool, filters=filters)
        return [(resource, max(0.0, 1.0 - distance)) for resource, distance in matches]

    @staticmethod
    def _build_query(request: RecommendationRequest, computed, gaps: dict[uuid.UUID, float]) -> str:
        gap_names = [computed.nodes[sid].name for sid in gaps if sid in computed.nodes]
        query = canonical_goal_query_text(title=request.goal_text, target_skill_names=gap_names)
        return query or " ".join(gap_names) or (request.goal_text or "learning resources")

    # --- candidate assembly ----------------------------------------------
    @staticmethod
    def _to_candidate(
        resource: Resource, similarity: float, provider_success: dict[str, float]
    ) -> CandidateResource:
        taught = tuple(
            TaughtSkill(
                skill_id=link.skill_id,
                level_from=min(1.0, max(0.0, link.teaches_level_from)),
                level_to=min(1.0, max(0.0, link.teaches_level_to)),
                coverage_weight=link.coverage_weight,
            )
            for link in resource.skills
        )
        prereqs = tuple(
            ResourcePrerequisite(skill_id=link.skill_id, min_proficiency=link.min_proficiency)
            for link in resource.prerequisites
        )
        return CandidateResource(
            resource_id=resource.id,
            semantic_similarity=similarity,
            taught=taught,
            prerequisites=prereqs,
            difficulty=resource.difficulty,
            modality=resource.modality.value,
            quality_score=resource.quality_score,
            rating=resource.rating,
            estimated_hours=resource.estimated_hours,
            historical_success=provider_success.get(resource.provider),
        )

    async def _already_learned(
        self, user_id: uuid.UUID, candidates: list[Resource]
    ) -> dict[uuid.UUID, str]:
        """Resources this learner has already done, from both histories.

        Recommending something the learner finished last week is the most
        obvious way for a recommender to look like it is not paying attention,
        so both the recorded event log and the profile's declared courses are
        consulted. Declared courses only suppress on an unambiguous match — see
        `engines/recommendation/history.py`.
        """
        completed = await self.progress.completed_resource_ids(user_id)

        profile = await self.profiles.get_by_user(user_id)
        declared_raw = list(profile.completed_courses or []) if profile else []
        declared = [
            DeclaredCourse(
                title=str(entry.get("title") or ""),
                provider=entry.get("provider"),
                url=entry.get("url"),
                resource_id=_as_uuid(entry.get("resource_id")),
            )
            for entry in declared_raw
            if isinstance(entry, dict)
        ]
        catalogue = [
            CatalogueEntry(
                resource_id=r.id, title=r.title, provider=r.provider, url=r.url
            )
            for r in candidates
        ]
        matches = match_declared_courses(declared, catalogue) if declared else {}
        return build_suppressions(completed, matches)

    async def _provider_success(self, user_id: uuid.UUID) -> dict[str, float]:
        """Per-provider success prior from the learner's own resource feedback.

        Empty when there is no history — the engine then uses its neutral prior.
        This is the "historical performance if available" signal.
        """
        rows = await self.feedback.list(
            limit=500,
            filters=[
                Feedback.user_id == user_id,
                Feedback.target_type == FeedbackTargetType.RESOURCE,
            ],
        )
        if not rows:
            return {}
        resources = {r.id: r for r in await self.resources.get_many([r.target_id for r in rows])}
        by_provider: dict[str, list[float]] = {}
        for row in rows:
            resource = resources.get(row.target_id)
            if resource is not None and row.signal in _FEEDBACK_VALUE:
                by_provider.setdefault(resource.provider, []).append(_FEEDBACK_VALUE[row.signal])
        return {p: sum(v) / len(v) for p, v in by_provider.items() if v}

    # --- response mapping ------------------------------------------------
    def _to_item(self, rc: RankedCandidate, *, rank: int) -> RecommendationItem:
        scored = rc.scored
        return RecommendationItem(
            resource=ResourceRead.model_validate(rc.resource),
            score=scored.score,
            rank=rank,
            is_ready=scored.is_ready,
            factors=scored.features,
            contributions=scored.contributions,
            matched_skills=self._skill_refs(rc.resource, scored.matched_gap_skill_ids, prereq=False),
            unmet_prerequisites=self._skill_refs(
                rc.resource, scored.unmet_prerequisite_ids, prereq=True
            ),
            reason=self.explain_ranking_factors(rc),
        )

    @staticmethod
    def _skill_refs(resource: Resource, skill_ids, *, prereq: bool) -> list[SkillRef]:
        links = resource.prerequisites if prereq else resource.skills
        by_id = {link.skill_id: link.skill for link in links if link.skill is not None}
        return [
            SkillRef(id=by_id[sid].id, slug=by_id[sid].slug, name=by_id[sid].name)
            for sid in skill_ids
            if sid in by_id
        ]

    @staticmethod
    def _skill_names(resource: Resource, skill_ids, *, prereq: bool) -> list[str]:
        links = resource.prerequisites if prereq else resource.skills
        by_id = {link.skill_id: link.skill for link in links if link.skill is not None}
        return [by_id[sid].name for sid in skill_ids if sid in by_id]

    def _weights_dict(self) -> dict[str, float]:
        w = self.weights
        return {
            "semantic_similarity": w.semantic_similarity,
            "skill_gap_match": w.skill_gap_match,
            "prerequisite_match": w.prerequisite_match,
            "difficulty_match": w.difficulty_match,
            "preference_match": w.preference_match,
            "quality_score": w.quality_score,
            "historical_success": w.historical_success,
            "time_fit": w.time_fit,
        }

    async def _persist(self, user_id: uuid.UUID, items: list[RecommendationItem]) -> None:
        """Store the ranked results as pending recommendations, replacing prior."""
        existing = await self.recommendations.list(
            limit=1000,
            filters=[
                Recommendation.user_id == user_id,
                Recommendation.status == RecommendationStatus.PENDING,
            ],
        )
        for row in existing:
            await self.session.delete(row)
        await self.session.flush()

        now = datetime.now(timezone.utc)
        for item in items:
            self.session.add(
                Recommendation(
                    user_id=user_id,
                    resource_id=item.resource.id,
                    skill_id=item.matched_skills[0].id if item.matched_skills else None,
                    score=item.score,
                    rank=item.rank,
                    reason=item.reason,
                    rationale_trace={
                        "factors": item.factors,
                        "contributions": item.contributions,
                    },
                    generated_at=now,
                )
            )
        await self.session.flush()
        await self.commit()

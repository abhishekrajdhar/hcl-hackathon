"""Keeping the resource catalogue populated and alive.

Two jobs, both background, neither on a request path:

  * **discovery** — a skill nothing teaches produces a "Self-study: X" milestone
    with nothing for the learner to actually do. That happens because the role
    designer invents skills at runtime whenever a goal needs one the catalogue
    lacks. Discovery closes the gap: search for the skill, verify the
    candidates, let the pure selector choose, persist what survives.
  * **health** — a video that goes private or is deleted becomes a dead link on
    somebody's roadmap, and nothing in the system would ever notice. Re-checking
    known ids is cheap enough to run nightly.

The split of labour is the same as everywhere else in this codebase: the
provider fetches, a pure engine decides, and only this service touches the
database. Discovery deliberately runs per *skill*, not per request — a search
costs real quota and its result is worth keeping forever, so paying for it
inside a learner's roadmap generation would be both slow and, at ~95 searches
a day, exhausted by ten learners.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.catalogue.base import CatalogueError, CatalogueProvider, QuotaExceededError, VideoRecord
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMError, LLMProvider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.engines.catalogue.select import Selection, select_videos, teaching_band
from app.models.enums import Modality, ResourceType
from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.models.goal import LearningGoalSkill
from app.models.skill import Skill
from app.repositories.resource import ResourceRepository
from app.repositories.skill import PrerequisiteRepository, SkillRepository
from app.services.base import BaseService

logger = get_logger(__name__)

#: Marks rows this pipeline created, so they can be told apart from the curated
#: seed and re-examined (or removed) without touching hand-picked content.
ORIGIN = "catalogue_pipeline"

#: Proficiency a prerequisite must reach before material of this difficulty is
#: a sensible next step. Intro material (1-2) is never gated — gating a
#: beginner course behind prerequisites is how a learner gets stuck. Same table
#: the seed generator uses, so discovered and seeded rows gate alike.
GATE_LEVEL = {3: 0.35, 4: 0.45, 5: 0.55}
#: At most this many prerequisites are attached, so a discovered resource never
#: becomes harder to unlock than a curated one.
MAX_PREREQS = 3


@dataclass(slots=True)
class SkillDiscovery:
    """What discovery did for one skill."""

    skill_slug: str
    searched: bool = False
    candidates: int = 0
    created: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class HealthReport:
    checked: int = 0
    deactivated: list[str] = field(default_factory=list)
    reactivated: list[str] = field(default_factory=list)
    #: Ids the provider could not speak to. Explicitly *not* deactivated:
    #: "we could not check" and "it is gone" must never be conflated.
    unknown: list[str] = field(default_factory=list)


#: How many engine-approved candidates the selection agent chooses among. More
#: than the final pick count so the model has real choices; small enough that
#: every candidate shown to it already passed every hard rule.
_AGENT_SHORTLIST = 6

_AGENT_SYSTEM_PROMPT = """You choose the best learning videos for a skill from a
shortlist. Every candidate already passed relevance, length and noise filters —
your job is judgement: prefer complete, well-structured courses from reputable
teaching channels over fragmentary or clickbait content, and prefer a set that
covers the skill from fundamentals upward. Return ONLY candidates from the
list, by their video_id."""

_AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "chosen": {
            "type": "array",
            "items": {"type": "string"},
            "description": "video_ids of the selected candidates, best first",
        }
    },
    "required": ["chosen"],
}


class CatalogueService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        provider: CatalogueProvider,
        llm: LLMProvider | None = None,
    ) -> None:
        super().__init__(session)
        self.provider = provider
        #: Optional judge over the pure selector's shortlist. The engine stays
        #: the floor: the model may only reorder/choose among candidates the
        #: engine already approved, and any invalid answer falls back to the
        #: engine's own ranking.
        self.llm = llm
        self.resources = ResourceRepository(session)
        self.skills = SkillRepository(session)
        self.prerequisites = PrerequisiteRepository(session)

    # --- discovery -------------------------------------------------------
    async def uncovered_skills(self) -> list[Skill]:
        """Skills nothing in the catalogue teaches, most in demand first.

        These are exactly the skills that would otherwise show up on a roadmap
        as a self-study placeholder. Ordering is by how many learners actually
        want the skill — a gap somebody is standing in front of today is worth
        a search before one nobody has asked for, and a search costs real
        quota. Ties break on slug so a run is reproducible.
        """
        taught = (
            select(ResourceSkill.skill_id)
            .join(Resource, Resource.id == ResourceSkill.resource_id)
            .where(Resource.is_active.is_(True))
        )
        wanted = (
            select(LearningGoalSkill.skill_id, func.count().label("n"))
            .group_by(LearningGoalSkill.skill_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(Skill)
            .outerjoin(wanted, wanted.c.skill_id == Skill.id)
            .where(Skill.id.not_in(taught))
            .order_by(func.coalesce(wanted.c.n, 0).desc(), Skill.difficulty.desc(), Skill.slug)
        )
        return list(rows.scalars().all())

    async def skill_by_slug(self, slug: str) -> Skill | None:
        return await self.skills.get_by_slug(slug)

    def _query_for(self, skill: Skill) -> str:
        """What to actually type into a search box for this skill.

        The skill name alone is often too abstract to match teaching content —
        "Game Engines & Frameworks" returns essays, "unity tutorial for
        beginners" returns lessons. The first alias, where one exists, is the
        concrete handle a human would use.
        """
        handle = (skill.aliases or [None])[0] or skill.name
        return f"{handle} tutorial full course for beginners"

    async def discover_for_skill(self, skill: Skill, *, picks: int = 2, search_limit: int = 10) -> SkillDiscovery:
        result = SkillDiscovery(skill_slug=skill.slug)
        try:
            ids = await self.provider.search(self._query_for(skill), limit=search_limit)
            result.searched = True
            if not ids:
                return result
            records = await self.provider.lookup(ids)
        except QuotaExceededError:
            raise
        except CatalogueError as exc:
            result.error = str(exc)[:200]
            logger.warning("discovery failed", extra={"skill": skill.slug, "error": result.error})
            return result

        result.candidates = len(records)
        existing = await self._existing_external_ids()
        shortlist = select_videos(
            records,
            skill.name,
            skill.aliases or (),
            limit=max(picks, _AGENT_SHORTLIST),
            exclude_ids=frozenset(existing),
            language=settings.CATALOGUE_LANGUAGE,
        )
        picked = await self._agent_pick(skill, shortlist, picks)
        for selection in picked:
            resource = await self._persist(selection, skill)
            result.created.append(resource.title)
        if picked:
            await self.commit()
        return result

    async def fill_gaps(self, *, max_skills: int = 10, picks: int = 2, search_limit: int = 10) -> list[SkillDiscovery]:
        """Run discovery over uncovered skills until the budget runs out."""
        results: list[SkillDiscovery] = []
        for skill in (await self.uncovered_skills())[:max_skills]:
            try:
                results.append(
                    await self.discover_for_skill(skill, picks=picks, search_limit=search_limit)
                )
            except QuotaExceededError as exc:
                # Stop the whole run: every remaining search would fail the same
                # way, and hammering a spent quota helps nobody.
                logger.warning("stopping discovery", extra={"reason": str(exc)})
                results.append(SkillDiscovery(skill_slug=skill.slug, error=str(exc)[:200]))
                break
        return results

    async def _agent_pick(
        self, skill: Skill, shortlist: list[Selection], picks: int
    ) -> list[Selection]:
        """The best `picks` from the engine-approved shortlist.

        With a model configured it acts as the judge — expert course taste over
        candidates the pure engine already vetted. Its answer is only accepted
        when every id it names is on the shortlist; anything else (no model,
        transport failure, invented ids) falls back to the engine's ranking,
        so the deterministic floor always stands.
        """
        if len(shortlist) <= picks or self.llm is None:
            return shortlist[:picks]

        by_id = {s.video.video_id: s for s in shortlist}
        candidates = [
            {
                "video_id": s.video.video_id,
                "title": s.video.title,
                "channel": s.video.channel,
                "hours": s.video.duration_hours,
                "views": s.video.view_count,
                "engine_score": s.score,
            }
            for s in shortlist
        ]
        try:
            completion = await self.llm.complete(
                system=_AGENT_SYSTEM_PROMPT,
                user=(
                    f"Skill to learn: {skill.name}\n"
                    f"Pick the best {picks} candidates.\n\n"
                    f"Candidates (JSON):\n{json.dumps(candidates, indent=2)}"
                ),
                json_schema=_AGENT_SCHEMA,
                max_tokens=300,
            )
            chosen_ids = extract_json_object(completion.text).get("chosen", [])
        except (LLMError, JsonExtractionError) as exc:
            logger.warning(
                "selection agent unavailable; using engine ranking",
                extra={"skill": skill.slug, "error": str(exc)[:200]},
            )
            return shortlist[:picks]

        chosen = [by_id[v] for v in chosen_ids if isinstance(v, str) and v in by_id]
        if not chosen:
            logger.warning(
                "selection agent answered off-shortlist; using engine ranking",
                extra={"skill": skill.slug},
            )
            return shortlist[:picks]
        return chosen[:picks]

    async def _existing_external_ids(self) -> set[str]:
        rows = await self.session.execute(
            select(Resource.external_id).where(Resource.external_id.is_not(None))
        )
        return {r for r in rows.scalars().all() if r}

    async def _persist(self, selection: Selection, skill: Skill) -> Resource:
        video = selection.video
        difficulty = max(1, min(5, skill.difficulty or 2))
        level_from, level_to = teaching_band(difficulty)

        resource = Resource(
            external_id=video.video_id,
            provider=video.channel or "YouTube",
            title=video.title[:512],
            description=(
                video.description[:500]
                or f"{selection.resource_type.title()} by {video.channel} on YouTube."
            ),
            url=video.url,
            resource_type=ResourceType(selection.resource_type),
            modality=Modality.VIDEO,
            difficulty=difficulty,
            estimated_hours=video.duration_hours,
            language="en",
            is_active=True,
            extra={
                "origin": ORIGIN,
                "discovered_for": skill.slug,
                "selection_score": selection.score,
                "selection_reasons": list(selection.reasons),
                "provider": self.provider.name,
            },
        )
        self.session.add(resource)
        await self.session.flush()

        self.session.add(
            ResourceSkill(
                resource_id=resource.id,
                skill_id=skill.id,
                teaches_level_from=level_from,
                teaches_level_to=level_to,
                coverage_weight=1.0,
                is_primary=True,
            )
        )
        for prereq_id, level in await self._gates_for(skill, difficulty):
            self.session.add(
                ResourcePrerequisite(
                    resource_id=resource.id, skill_id=prereq_id, min_proficiency=level
                )
            )
        await self.session.flush()
        logger.info(
            "discovered resource",
            extra={"skill": skill.slug, "video": video.video_id, "score": selection.score},
        )
        return resource

    async def _gates_for(self, skill: Skill, difficulty: int) -> list[tuple[uuid.UUID, float]]:
        """Prerequisites for a discovered resource, taken from the live skill
        graph rather than from the seed — so a resource gates on whatever the
        graph currently says, including edges the role designer added."""
        level = GATE_LEVEL.get(difficulty)
        if level is None:
            return []
        edges = await self.prerequisites.list_prerequisites(skill.id)
        hard = [e for e in edges if e.relationship_type.value == "hard_prerequisite"]
        return [(e.prerequisite_skill_id, level) for e in hard[:MAX_PREREQS]]

    # --- health ----------------------------------------------------------
    async def health_check(
        self,
        *,
        include_inactive: bool = True,
        external_ids: Sequence[str] | None = None,
        apply: bool = True,
    ) -> HealthReport:
        """Re-check catalogue videos against the provider.

        Deactivates rows whose video is gone or has been made private, and
        brings back rows that have returned. Rows the provider had nothing to
        say about are reported as unknown and left exactly as they were.

        `external_ids` narrows the run to specific videos. Without it the scope
        is the whole catalogue, which is right for a nightly job and dangerous
        for anything else: a caller holding a provider that only knows about a
        few videos will otherwise ask it about every row and act on the answer.

        `apply=False` produces the same report — same provider calls, same
        evidence rules — but writes nothing, so an operator can see what a
        nightly run would do before letting it do it.
        """
        report = HealthReport()
        filters = [Resource.external_id.is_not(None), Resource.url.like("%youtube.com%")]
        if external_ids is not None:
            filters.append(Resource.external_id.in_(list(external_ids)))
        if not include_inactive:
            filters.append(Resource.is_active.is_(True))
        rows = await self.session.execute(select(Resource).where(*filters))
        catalogue = {r.external_id: r for r in rows.scalars().all() if r.external_id}
        if not catalogue:
            return report

        try:
            records = await self.provider.lookup(list(catalogue))
        except CatalogueError as exc:
            logger.warning("health check failed", extra={"error": str(exc)[:200]})
            report.unknown = list(catalogue)
            return report

        seen = {r.video_id: r for r in records}
        report.checked = len(catalogue)
        for external_id, resource in catalogue.items():
            record = seen.get(external_id)
            if record is None:
                report.unknown.append(external_id)
                continue
            self._apply_health(resource, record, report, apply=apply)
        if apply:
            await self.commit()
        return report

    def _may_deactivate(self) -> bool:
        """Only a provider that can prove absence may take a resource offline.

        A scraper reporting "unavailable" is reporting that it got no usable
        answer, which a rate limiter produces in bulk. Acting on that once
        deactivated 89 working videos in a single run.
        """
        return self.provider.can_prove_absence

    def _apply_health(
        self, resource: Resource, record: VideoRecord, report: HealthReport, *, apply: bool
    ) -> None:
        if record.is_available and not resource.is_active:
            # Bringing a resource back is safe from any provider: a successful
            # fetch is positive evidence however it was obtained.
            if apply:
                resource.is_active = True
            report.reactivated.append(resource.title)
        elif not record.is_available and resource.is_active:
            if not self._may_deactivate():
                report.unknown.append(record.video_id)
                return
            if apply:
                resource.is_active = False
                resource.extra = {
                    **(resource.extra or {}),
                    "deactivated_reason": "unavailable upstream",
                }
            report.deactivated.append(resource.title)
            logger.warning(
                "resource no longer available upstream",
                extra={"video": record.video_id, "title": resource.title[:60]},
            )

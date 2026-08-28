"""Learner Profile Engine.

Owns the learner's structured profile and their skill-proficiency vector, and
the deterministic rules that keep proficiency current — including the update
that runs after an assessment. Proficiency is the canonical [0, 1] value; the
0..level_scale `current_level` is kept in sync for the prerequisite/gap engines.

The LLM never touches the database. A conversation is turned into a validated
`ProfileDraft` by some extractor, and `apply_draft` folds that draft in with the
same deterministic code the API uses.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.engines.adaptive import recover_previous, update_from_assessment
from app.engines.profile import (
    ProfileSnapshot,
    assessment_skill_scores,
    clamp01,
    evidence_strength,
    proficiency_to_level,
    validate_profile,
)
from app.models.assessment import AssessmentResult
from app.models.enums import EvidenceSource
from app.models.skill import Skill, UserSkill
from app.models.user import LearnerProfile
from app.repositories.assessment import AssessmentRepository, AssessmentResultRepository
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.repositories.user import LearnerProfileRepository, UserRepository
from app.schemas.profile import (
    AssessmentHistoryItem,
    AssessmentHistorySummary,
    FullLearnerProfile,
    LearnerProfileCreate,
    LearnerProfileRead,
    LearnerProfileUpdate,
    ProficiencyChange,
    ProficiencyUpdateReport,
    ProfileDraft,
    ProfileDraftPreview,
    ProfileValidationRead,
    SkillProficiencyCreate,
    SkillProficiencyRead,
    SkillProficiencyUpdate,
    ValidationIssueRead,
)
from app.services.base import BaseService

#: Confidence assigned to a brand-new skill created purely from one assessment.
_NEW_SKILL_CONFIDENCE = 0.3
#: Recent assessment attempts surfaced in the aggregate profile.
_RECENT_HISTORY_LIMIT = 10


class ProfileService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.profiles = LearnerProfileRepository(session)
        self.user_skills = UserSkillRepository(session)
        self.skills = SkillRepository(session)
        self.results = AssessmentResultRepository(session)
        self.assessments = AssessmentRepository(session)
        self.users = UserRepository(session)

    # --- helpers ---------------------------------------------------------
    async def _require_user(self, user_id: uuid.UUID) -> None:
        if await self.users.get(user_id) is None:
            raise NotFoundError("User", user_id)

    @staticmethod
    def _dump_profile_payload(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested Pydantic sub-models (courses/projects) to JSON-able dicts."""
        for key in ("completed_courses", "completed_projects"):
            if key in data and data[key] is not None:
                data[key] = [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                    for item in data[key]
                ]
        return data

    # --- profile CRUD ----------------------------------------------------
    async def get_for_user(self, user_id: uuid.UUID) -> LearnerProfile:
        profile = await self.profiles.get_by_user(user_id)
        if profile is None:
            raise NotFoundError("Learner profile for this user")
        return profile

    async def create_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileCreate
    ) -> LearnerProfile:
        await self._require_user(user_id)
        if await self.profiles.get_by_user(user_id) is not None:
            raise ConflictError(
                "This user already has a profile; update it instead",
                error_code="profile_exists",
            )
        data = self._dump_profile_payload(payload.model_dump())
        profile = await self.profiles.create({**data, "user_id": user_id})
        await self.commit()
        return profile

    async def update_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileUpdate
    ) -> LearnerProfile:
        profile = await self.get_for_user(user_id)
        data = self._dump_profile_payload(payload.model_dump(exclude_unset=True))
        if data:
            data["version"] = profile.version + 1
            await self.profiles.update(profile, data)
            await self.commit()
        return profile

    async def upsert_for_user(
        self, user_id: uuid.UUID, payload: LearnerProfileCreate
    ) -> LearnerProfile:
        await self._require_user(user_id)
        existing = await self.profiles.get_by_user(user_id)
        if existing is None:
            return await self.create_for_user(user_id, payload)
        data = self._dump_profile_payload(payload.model_dump())
        await self.profiles.update(existing, {**data, "version": existing.version + 1})
        await self.commit()
        return existing

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile = await self.get_for_user(user_id)
        await self.profiles.delete(profile)
        await self.commit()

    # --- aggregate view --------------------------------------------------
    async def get_full_profile(self, user_id: uuid.UUID) -> FullLearnerProfile:
        profile = await self.get_for_user(user_id)
        skills = await self.user_skills.list(
            limit=1000,
            filters=[UserSkill.user_id == user_id],
            order_by=(UserSkill.proficiency.desc(),),
        )
        history = await self._assessment_history(user_id)
        return FullLearnerProfile(
            profile=LearnerProfileRead.model_validate(profile),
            skills=[self._to_proficiency_read(s) for s in skills],
            skill_count=len(skills),
            assessment_history=history,
        )

    async def _assessment_history(self, user_id: uuid.UUID) -> AssessmentHistorySummary:
        results = await self.results.list_for_user(
            user_id, limit=_RECENT_HISTORY_LIMIT, offset=0
        )
        total = await self.results.count([AssessmentResult.user_id == user_id])
        if total == 0:
            return AssessmentHistorySummary()

        # `results` is only the recent page; summarise over it for the average
        # and passed-count shown alongside the recent list.
        passed = sum(1 for r in results if r.passed)
        avg = sum(r.percentage for r in results) / len(results) if results else 0.0
        return AssessmentHistorySummary(
            total_attempts=total,
            passed_attempts=passed,
            average_percentage=round(avg, 4),
            last_attempt_at=results[0].submitted_at if results else None,
            recent=[AssessmentHistoryItem.model_validate(r) for r in results],
        )

    # --- validation ------------------------------------------------------
    async def validate(self, user_id: uuid.UUID, *, today: date | None = None) -> ProfileValidationRead:
        profile = await self.get_for_user(user_id)
        skills = await self.user_skills.list(
            limit=1000, filters=[UserSkill.user_id == user_id]
        )
        proficiencies = tuple(s.proficiency for s in skills)
        snapshot = ProfileSnapshot(
            weekly_hours=profile.weekly_hours,
            experience_level=profile.experience_level.value,
            target_deadline=profile.target_deadline,
            goal_text_raw=profile.goal_text_raw,
            target_role=profile.target_role,
            interests=tuple(profile.interests),
            preferred_modalities=tuple(profile.preferred_modalities),
            skill_count=len(skills),
            max_proficiency=max(proficiencies, default=0.0),
            proficiencies=proficiencies,
        )
        result = validate_profile(snapshot, today=today or datetime.now(timezone.utc).date())
        return ProfileValidationRead(
            is_valid=result.is_valid,
            errors=[ValidationIssueRead(**dataclasses.asdict(i)) for i in result.errors],
            warnings=[ValidationIssueRead(**dataclasses.asdict(i)) for i in result.warnings],
        )

    # --- skill proficiency (0..1) ----------------------------------------
    @staticmethod
    def _to_proficiency_read(entry: UserSkill) -> SkillProficiencyRead:
        return SkillProficiencyRead.model_validate(
            {
                "skill_id": entry.skill_id,
                "proficiency": entry.proficiency,
                "confidence": entry.confidence,
                "evidence_source": entry.evidence_source,
                "target_proficiency": (
                    round(entry.target_level / entry.skill.level_scale, 4)
                    if entry.target_level is not None and entry.skill and entry.skill.level_scale
                    else None
                ),
                "last_practiced_at": entry.last_practiced_at,
                "notes": entry.notes,
                "updated_at": entry.updated_at,
                "skill": entry.skill,
            }
        )

    async def list_skills(self, user_id: uuid.UUID) -> list[SkillProficiencyRead]:
        skills = await self.user_skills.list(
            limit=1000,
            filters=[UserSkill.user_id == user_id],
            order_by=(UserSkill.proficiency.desc(),),
        )
        return [self._to_proficiency_read(s) for s in skills]

    async def get_skill(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> SkillProficiencyRead:
        entry = await self.user_skills.get_for_user(user_id, skill_id)
        if entry is None:
            raise NotFoundError("Skill proficiency for this user", skill_id)
        return self._to_proficiency_read(entry)

    async def set_skill_proficiency(
        self, user_id: uuid.UUID, payload: SkillProficiencyCreate
    ) -> SkillProficiencyRead:
        """Create a skill proficiency. Fails if one already exists (use PUT)."""
        await self._require_user(user_id)
        skill = await self.skills.get(payload.skill_id)
        if skill is None:
            raise NotFoundError("Skill", payload.skill_id)
        if await self.user_skills.get_for_user(user_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already on the learner's profile; update it instead",
                error_code="user_skill_exists",
            )
        await self._write_proficiency(
            user_id,
            skill,
            proficiency=payload.proficiency,
            confidence=payload.confidence,
            evidence_source=payload.evidence_source,
            target_proficiency=payload.target_proficiency,
            notes=payload.notes,
        )
        await self.commit()
        return await self.get_skill(user_id, payload.skill_id)

    async def upsert_skill_proficiency(
        self, user_id: uuid.UUID, skill_id: uuid.UUID, payload: SkillProficiencyUpdate
    ) -> SkillProficiencyRead:
        """Authoritative set/replace of a skill's proficiency (PUT)."""
        await self._require_user(user_id)
        skill = await self.skills.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        existing = await self.user_skills.get_for_user(user_id, skill_id)

        if existing is None:
            if payload.proficiency is None:
                raise NotFoundError("Skill proficiency for this user", skill_id)
            await self._write_proficiency(
                user_id,
                skill,
                proficiency=payload.proficiency,
                confidence=payload.confidence if payload.confidence is not None else 0.6,
                evidence_source=payload.evidence_source or EvidenceSource.SELF_REPORT,
                target_proficiency=payload.target_proficiency,
                notes=payload.notes,
            )
        else:
            self._apply_proficiency_update(existing, skill, payload)
            await self.session.flush()

        await self.commit()
        return await self.get_skill(user_id, skill_id)

    def _apply_proficiency_update(
        self, entry: UserSkill, skill: Skill, payload: SkillProficiencyUpdate
    ) -> None:
        if payload.proficiency is not None:
            entry.proficiency = payload.proficiency
            entry.current_level = proficiency_to_level(payload.proficiency, skill.level_scale)
        if payload.confidence is not None:
            entry.confidence = payload.confidence
        if payload.evidence_source is not None:
            entry.evidence_source = payload.evidence_source
        if payload.target_proficiency is not None:
            entry.target_level = proficiency_to_level(payload.target_proficiency, skill.level_scale)
        if payload.notes is not None:
            entry.notes = payload.notes

    async def _write_proficiency(
        self,
        user_id: uuid.UUID,
        skill: Skill,
        *,
        proficiency: float,
        confidence: float,
        evidence_source: EvidenceSource,
        target_proficiency: float | None = None,
        notes: str | None = None,
        last_practiced_at: datetime | None = None,
    ) -> UserSkill:
        """Insert a UserSkill from a [0, 1] proficiency, syncing current_level."""
        return await self.user_skills.create(
            {
                "user_id": user_id,
                "skill_id": skill.id,
                "proficiency": proficiency,
                "current_level": proficiency_to_level(proficiency, skill.level_scale),
                "confidence": confidence,
                "evidence_source": evidence_source,
                "target_level": (
                    proficiency_to_level(target_proficiency, skill.level_scale)
                    if target_proficiency is not None
                    else None
                ),
                "notes": notes,
                "last_practiced_at": last_practiced_at,
            }
        )

    async def delete_skill(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        entry = await self.user_skills.get_for_user(user_id, skill_id)
        if entry is None:
            raise NotFoundError("Skill proficiency for this user", skill_id)
        await self.user_skills.delete(entry)
        await self.commit()

    # --- assessment-driven update ---------------------------------------
    async def update_proficiency_from_assessment(
        self, user_id: uuid.UUID, result: AssessmentResult
    ) -> ProficiencyUpdateReport:
        """Fold an assessment result into the learner's proficiency vector.

        Deterministic MVP rule (spec): new = 0.6*old + 0.4*assessment_score,
        applied per assessed skill. Every change is reported for auditing.
        Commits its own transaction.
        """
        assessment = await self.assessments.get(result.assessment_id)
        fallback_skill_id = assessment.skill_id if assessment else None
        scores = assessment_skill_scores(
            result.responses, fallback_skill_id=fallback_skill_id
        )
        now = datetime.now(timezone.utc)
        changes: list[ProficiencyChange] = []

        for score in scores:
            skill = await self.skills.get(score.skill_id)
            if skill is None:
                continue  # question tagged to a since-deleted skill

            entry = await self.user_skills.get_for_user(user_id, score.skill_id)
            strength = evidence_strength(score.total)  # confidence grows with more questions

            if entry is None:
                previous = 0.0
                new_proficiency = update_from_assessment(previous, score.ratio)
                await self._write_proficiency(
                    user_id,
                    skill,
                    proficiency=new_proficiency,
                    confidence=clamp01(_NEW_SKILL_CONFIDENCE + strength * (1 - _NEW_SKILL_CONFIDENCE)),
                    evidence_source=EvidenceSource.ASSESSMENT,
                    last_practiced_at=now,
                )
                changes.append(
                    ProficiencyChange(
                        skill_id=score.skill_id,
                        previous_proficiency=previous,
                        new_proficiency=new_proficiency,
                        delta=round(new_proficiency - previous, 6),
                        observed=score.ratio,
                        evidence_source=EvidenceSource.ASSESSMENT,
                        created=True,
                    )
                )
            else:
                previous = entry.proficiency
                new_proficiency = update_from_assessment(previous, score.ratio)
                entry.proficiency = new_proficiency
                entry.current_level = proficiency_to_level(new_proficiency, skill.level_scale)
                entry.confidence = clamp01(entry.confidence + strength * (1 - entry.confidence))
                entry.evidence_source = EvidenceSource.ASSESSMENT
                entry.last_practiced_at = now
                await self.session.flush()
                changes.append(
                    ProficiencyChange(
                        skill_id=score.skill_id,
                        previous_proficiency=round(previous, 6),
                        new_proficiency=new_proficiency,
                        delta=round(new_proficiency - previous, 6),
                        observed=score.ratio,
                        evidence_source=EvidenceSource.ASSESSMENT,
                        created=False,
                    )
                )

        await self.commit()
        return ProficiencyUpdateReport(
            user_id=user_id, source=f"assessment:{result.assessment_id}", changes=changes
        )

    async def reapply_assessment_ratio(
        self,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        old_ratio: float,
        new_ratio: float,
    ) -> ProficiencyChange | None:
        """Replace an already-applied assessment update after a reviewer
        re-scores the attempt.

        The submission blended `old_ratio` into the proficiency; the reviewer
        has now changed the score for this skill. Because the blend is a fixed
        linear formula, the pre-submission value is recoverable exactly —
        recover it with the OLD ratio, re-apply with the NEW one. Reviewing
        the same answer twice cannot double-apply: the recovery always inverts
        exactly one application.
        """
        skill = await self.skills.get(skill_id)
        if skill is None:
            return None
        entry = await self.user_skills.get_for_user(user_id, skill_id)
        if entry is None:
            # Submission never wrote this skill (deleted at the time?);
            # apply the reviewed score as a fresh observation.
            new_proficiency = update_from_assessment(0.0, new_ratio)
            await self._write_proficiency(
                user_id, skill,
                proficiency=new_proficiency,
                confidence=_NEW_SKILL_CONFIDENCE,
                evidence_source=EvidenceSource.ASSESSMENT,
                last_practiced_at=datetime.now(timezone.utc),
            )
            previous = 0.0
        else:
            previous = recover_previous(entry.proficiency, old_ratio)
            new_proficiency = update_from_assessment(previous, new_ratio)
            entry.proficiency = new_proficiency
            entry.current_level = proficiency_to_level(new_proficiency, skill.level_scale)
            entry.evidence_source = EvidenceSource.ASSESSMENT
            await self.session.flush()
        return ProficiencyChange(
            skill_id=skill_id,
            previous_proficiency=round(previous, 6),
            new_proficiency=new_proficiency,
            delta=round(new_proficiency - previous, 6),
            observed=new_ratio,
            evidence_source=EvidenceSource.ASSESSMENT,
            created=entry is None,
        )

    # --- draft ingestion (the LLM abstraction) ---------------------------
    async def apply_draft(
        self, user_id: uuid.UUID, draft: ProfileDraft
    ) -> ProfileDraftPreview:
        """Apply a validated ProfileDraft to the profile and skill vector.

        This is the single write path for any populate-from-conversation source.
        The draft is already schema-validated; here we resolve skill references
        deterministically, apply scalar fields, and upsert skill proficiencies as
        inferred evidence. Nothing about the extraction is trusted beyond the
        typed contract.
        """
        await self._require_user(user_id)
        profile = await self.profiles.get_by_user(user_id)
        if profile is None:
            profile = await self.profiles.create(
                {"user_id": user_id, "version": 1}
            )

        scalar_fields = draft.model_dump(
            exclude={"skills", "source_model", "extraction_confidence"},
            exclude_none=True,
        )
        scalar_fields = self._dump_profile_payload(scalar_fields)
        for key, value in scalar_fields.items():
            setattr(profile, key, value)
        if draft.source_model is not None:
            profile.extraction_model = draft.source_model
        if draft.extraction_confidence is not None:
            profile.extraction_confidence = draft.extraction_confidence
        profile.version += 1
        await self.session.flush()

        unresolved: list[str] = []
        for skill_draft in draft.skills:
            skill = await self._resolve_skill(skill_draft.skill_id, skill_draft.skill_ref)
            if skill is None:
                if skill_draft.skill_ref:
                    unresolved.append(skill_draft.skill_ref)
                continue
            existing = await self.user_skills.get_for_user(user_id, skill.id)
            if existing is None:
                await self._write_proficiency(
                    user_id,
                    skill,
                    proficiency=skill_draft.proficiency,
                    confidence=skill_draft.confidence,
                    evidence_source=EvidenceSource.INFERRED,
                )
            else:
                existing.proficiency = skill_draft.proficiency
                existing.current_level = proficiency_to_level(
                    skill_draft.proficiency, skill.level_scale
                )
                existing.confidence = skill_draft.confidence
                existing.evidence_source = EvidenceSource.INFERRED
                await self.session.flush()

        await self.commit()
        return ProfileDraftPreview(draft=draft, unresolved_skill_refs=unresolved, applied=True)

    async def _resolve_skill(
        self, skill_id: uuid.UUID | None, skill_ref: str | None
    ) -> Skill | None:
        """Resolve a draft skill reference to a canonical skill, deterministically."""
        if skill_id is not None:
            return await self.skills.get(skill_id)
        if not skill_ref:
            return None
        ref = skill_ref.strip().lower()
        by_slug = await self.skills.get_by_slug(ref)
        if by_slug is not None:
            return by_slug
        # Fall back to an exact name/alias match, ordered for determinism.
        matches = await self.skills.list(
            limit=1,
            filters=[SkillRepository.search_filter(ref)],
            order_by=(Skill.difficulty, Skill.slug),
        )
        return matches[0] if matches else None

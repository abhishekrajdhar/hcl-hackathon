"""Career readiness — evidence gathering for the pure readiness engine.

Collects what already exists (the active path's target vector, the skill twin,
assessment history, project items, pace) and hands it to
`engines/readiness/report.py`. No new state is stored: readiness is derived,
so it can never disagree with the evidence behind it.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.engines.progress import compute_pace, CompletedEffort
from app.engines.readiness import ReadinessReport, TargetSkill, compute_readiness
from app.models.enums import ResourceType
from app.repositories.assessment import AssessmentResultRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.progress import UserProgressRepository
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.services.base import BaseService


class ReadinessService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.paths = LearningPathRepository(session)
        self.items = LearningPathItemRepository(session)
        self.results = AssessmentResultRepository(session)
        self.progress = UserProgressRepository(session)
        self.skills = SkillRepository(session)
        self.user_skills = UserSkillRepository(session)

    async def report(self, user_id: uuid.UUID) -> ReadinessReport:
        path = await self.paths.get_active_for_user(user_id)
        if path is None:
            raise NotFoundError("Active learning path for this user")

        # --- target vector vs the skill twin ------------------------------
        snapshot = path.constraints_snapshot or {}
        raw_targets = snapshot.get("target_skills", [])
        target_ids = [uuid.UUID(t["skill_id"]) for t in raw_targets if t.get("skill_id")]
        skills_by_id = {s.id: s for s in await self.skills.get_many(target_ids)}
        from app.models.skill import UserSkill

        rows = await self.user_skills.list(
            limit=1000, filters=[UserSkill.user_id == user_id]
        )
        current = {us.skill_id: us.proficiency for us in rows}
        targets = [
            TargetSkill(
                skill_id=str(sid),
                name=skills_by_id[sid].name,
                required_level=float(t.get("required_level", 0.8)),
                current_level=float(current.get(sid, 0.0)),
            )
            for t, sid in ((t, uuid.UUID(t["skill_id"])) for t in raw_targets if t.get("skill_id"))
            if sid in skills_by_id
        ]

        # --- assessments ---------------------------------------------------
        results = await self.results.list_for_user(user_id, limit=50, offset=0)
        percentages = [r.percentage / 100 for r in results if r.max_score]

        # --- projects ------------------------------------------------------
        path_items = await self.items.list_for_path(path.id)
        completed_ids = await self.progress.completed_item_ids(user_id, path.id)
        project_items = [
            item for item in path_items
            if item.resource is not None and item.resource.resource_type == ResourceType.PROJECT
        ]
        projects_done = sum(1 for item in project_items if item.id in completed_ids)

        # --- momentum ------------------------------------------------------
        actual = await self.progress.minutes_per_completed_item(user_id, path.id)
        pace = compute_pace([
            CompletedEffort(
                estimated_minutes=item.estimated_minutes,
                actual_minutes=actual.get(item.id, 0),
            )
            for item in path_items
            if item.id in completed_ids
        ])

        return compute_readiness(
            targets=targets,
            assessment_percentages=percentages,
            projects_completed=projects_done,
            projects_total=len(project_items),
            pace_label=pace.label,
        )

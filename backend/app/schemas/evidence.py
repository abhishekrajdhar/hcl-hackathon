"""Skill-evidence response shapes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    #: self_report | assessment | completion | inferred
    kind: str
    label: str
    detail: str
    occurred_at: datetime | None = None


class SkillEvidenceRead(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    skill_slug: str
    proficiency: float
    confidence: float
    evidence: list[EvidenceItem]

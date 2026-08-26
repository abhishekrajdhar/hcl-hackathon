"""Career-readiness response shapes."""

from __future__ import annotations

from pydantic import BaseModel


class ReadinessDimensionRead(BaseModel):
    key: str
    label: str
    #: 0..1, or null when there is no evidence for this dimension yet.
    score: float | None
    detail: str


class ReadinessSkillRead(BaseModel):
    skill_id: str
    name: str
    required_level: float
    current_level: float
    readiness: float


class ReadinessReportRead(BaseModel):
    overall: float
    dimensions: list[ReadinessDimensionRead]
    skills: list[ReadinessSkillRead]
    weakest: str | None

"""Tests for the recommendation explainability layer: evidence, grounding, kinds."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.deps import get_llm_provider_dep
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.engines.explanation import check_grounding, render_template
from app.llm.providers.mock import MockProvider
from app.main import app
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.models.skill import UserSkill
from app.repositories.resource import ResourceRepository
from app.repositories.skill import SkillRepository
from app.repositories.user import LearnerProfileRepository, UserRepository
from app.schemas.explanation import (
    PrerequisiteRelation,
    RecommendationEvidence,
    ResourceSkillFact,
)

PW = "expl-pw-12345"


# --- pure grounding + templates (no DB) ------------------------------------
def _evidence() -> RecommendationEvidence:
    return RecommendationEvidence(
        recommendation_id=uuid.uuid4(),
        resource_title="Deep Learning with PyTorch",
        resource_type="course",
        resource_difficulty=4,
        learner_skill="Deep Learning",
        current_level=0.18,
        required_level=0.70,
        skill_gap=0.52,
        prerequisite_relationships=[
            PrerequisiteRelation(skill="Machine Learning", relationship="hard_prerequisite",
                                 status="met", learner_level=0.7, required_level=0.5),
        ],
        resource_skills=[ResourceSkillFact(skill="PyTorch", teaches_from=0.0, teaches_to=0.6)],
        goal="Computer Vision Engineer",
        strengths=["Python"],
    )


def test_template_uses_only_evidence_facts() -> None:
    text_ = render_template(_evidence(), "why_course")
    assert "18%" in text_ and "70%" in text_
    assert "PyTorch" in text_
    assert "Python" in text_


def test_grounding_accepts_supported_and_rejects_unsupported() -> None:
    evidence = _evidence()
    levels = [evidence.current_level, evidence.required_level, evidence.skill_gap]
    terms = ["Deep Learning", "PyTorch", "Python", "Machine Learning", "Computer Vision Engineer"]

    ok = check_grounding(
        "Your Deep Learning is 18% but the goal needs 70%. This covers PyTorch.",
        allowed_levels=levels, allowed_terms=terms,
    )
    assert ok.grounded

    bad = check_grounding(
        "This makes you 99% expert in Quantum Computing.",
        allowed_levels=levels, allowed_terms=terms,
    )
    assert not bad.grounded
    assert 99.0 in bad.unsupported_percentages
    assert any("Quantum" in t for t in bad.unsupported_terms)


def test_every_template_is_grounded_by_construction() -> None:
    evidence = _evidence()
    levels = [evidence.current_level, evidence.required_level, evidence.skill_gap]
    for rel in evidence.prerequisite_relationships:
        levels += [rel.learner_level, rel.required_level]
    for rs in evidence.resource_skills:
        levels += [rs.teaches_from, rs.teaches_to]
    terms = ["Deep Learning", "PyTorch", "Python", "Machine Learning", "Computer Vision Engineer",
             "Deep Learning with PyTorch", "course"]
    for kind in ("why_course", "why_now", "why_order", "why_project", "why_assessment"):
        text_ = render_template(evidence, kind)
        assert check_grounding(text_, allowed_levels=levels, allowed_terms=terms).grounded, kind


# --- API -------------------------------------------------------------------
async def _seeded() -> bool:
    try:
        async with SessionLocal() as s:
            return bool(await s.scalar(text("SELECT count(*) FROM resources")))
    except Exception:
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_db() -> None:
    if not await _seeded():
        pytest.skip("database not reachable or not seeded", allow_module_level=True)


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.pop(get_llm_provider_dep, None)


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as c:
        yield c


async def _learner_with_recommendation() -> tuple[uuid.UUID, str, uuid.UUID]:
    email = f"expl-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        user = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW)})
        await s.flush()
        await LearnerProfileRepository(s).create({"user_id": user.id, "target_role": "CV Engineer"})
        skills = SkillRepository(s)
        py = await skills.get_by_slug("python")
        dl = await skills.get_by_slug("deep-learning")
        s.add(UserSkill(user_id=user.id, skill_id=py.id, proficiency=0.85, current_level=4.25, confidence=0.8))
        s.add(UserSkill(user_id=user.id, skill_id=dl.id, proficiency=0.18, current_level=0.9, confidence=0.4))
        res = (await ResourceRepository(s).list(limit=1, filters=[Resource.title.ilike("%PyTorch%")]))[0]
        rec = Recommendation(user_id=user.id, resource_id=res.id, skill_id=dl.id, score=0.8, rank=0)
        s.add(rec)
        await s.commit()
        return user.id, email, rec.id


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_explanation_endpoint_returns_evidence_and_text(api: AsyncClient) -> None:
    uid, email, rec_id = await _learner_with_recommendation()
    h = await _auth(api, email)
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(responses=["irrelevant"])
    r = await api.post(f"/recommendations/{rec_id}/explanation", headers=h,
                       json={"kind": "why_course", "use_llm": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["explanation"]
    assert body["grounded"] is True
    ev = body["evidence"]
    assert ev["learner_skill"] == "Deep Learning"
    assert round(ev["current_level"], 2) == 0.18
    assert ev["skill_gap"] > 0
    assert any(rs["skill"] == "PyTorch" for rs in ev["resource_skills"])
    assert "Python" in ev["strengths"]


async def test_hallucinated_llm_explanation_is_rejected(api: AsyncClient) -> None:
    uid, email, rec_id = await _learner_with_recommendation()
    h = await _auth(api, email)
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(
        responses=["This makes you 99% proficient in Quantum Computing overnight."]
    )
    r = await api.post(f"/recommendations/{rec_id}/explanation", headers=h, json={"kind": "why_course"})
    assert r.status_code == 200
    # ungrounded claim rejected -> deterministic template returned
    assert r.json()["source"] == "template"
    assert "Quantum" not in r.json()["explanation"]


async def test_grounded_llm_explanation_is_used(api: AsyncClient) -> None:
    uid, email, rec_id = await _learner_with_recommendation()
    h = await _auth(api, email)
    grounded = "You already know Python. Your Deep Learning is about 18% versus a target near 70%. This resource covers PyTorch."
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(responses=[grounded])
    r = await api.post(f"/recommendations/{rec_id}/explanation", headers=h, json={"kind": "why_course"})
    assert r.json()["source"] == "llm"
    assert r.json()["grounded"] is True


async def test_all_explanation_kinds(api: AsyncClient) -> None:
    uid, email, rec_id = await _learner_with_recommendation()
    h = await _auth(api, email)
    for kind in ("why_course", "why_now", "why_order", "why_project", "why_assessment"):
        r = await api.post(f"/recommendations/{rec_id}/explanation", headers=h,
                           json={"kind": kind, "use_llm": False})
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == kind
        assert r.json()["explanation"]


async def test_cannot_explain_another_users_recommendation(api: AsyncClient) -> None:
    _, _, rec_id = await _learner_with_recommendation()
    other_email = f"other-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        await UserRepository(s).create({"email": other_email, "hashed_password": hash_password(PW)})
        await s.commit()
    other_h = await _auth(api, other_email)
    r = await api.post(f"/recommendations/{rec_id}/explanation", headers=other_h,
                       json={"kind": "why_course", "use_llm": False})
    assert r.status_code == 403

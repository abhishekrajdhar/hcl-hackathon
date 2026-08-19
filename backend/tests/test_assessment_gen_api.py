"""Integration tests for assessment generation, submit report, and results."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.deps import get_llm_provider_dep
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.llm.providers.mock import MockProvider
from app.main import app
from app.models.enums import UserRole
from app.repositories.user import UserRepository

pytestmark = pytest.mark.asyncio
PW = "assess-pw-12345"


async def _seeded() -> bool:
    try:
        async with SessionLocal() as s:
            return bool(await s.scalar(text("SELECT count(*) FROM skills")))
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


async def _user(role: UserRole = UserRole.LEARNER) -> tuple[uuid.UUID, str]:
    email = f"{role.value}-as-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        u = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW), "role": role})
        await s.commit()
        return u.id, email


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _answer_key(api: AsyncClient, admin: dict, assessment_id: str) -> list[dict]:
    r = await api.get(f"/assessments/{assessment_id}/questions", headers=admin)
    return sorted(r.json(), key=lambda q: q["order_index"])


# --- generation ------------------------------------------------------------
async def test_generate_template_assessment(api: AsyncClient) -> None:
    _, email = await _user()
    h = await _auth(api, email)
    r = await api.post(
        "/assessments/generate", headers=h,
        json={"skill_slug": "machine-learning", "num_questions": 5, "difficulty": 2, "use_llm": False},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["question_count"] == 5
    assert body["source"] == "template"

    # the generated questions are gradeable (learner view hides the answer key)
    detail = await api.get(f"/assessments/{body['assessment_id']}", headers=h)
    assert detail.json()["question_count"] == 5
    for q in detail.json()["questions"]:
        assert "correct_answer" not in q
        assert len(q["options"]) >= 2


async def test_generate_via_llm_validated(api: AsyncClient) -> None:
    _, email = await _user()
    h = await _auth(api, email)
    # a valid LLM response drives the LLM path
    canned = json.dumps({
        "questions": [
            {"stem": "What is supervised learning?",
             "options": [{"key": "a", "text": "Learning from labeled data"},
                         {"key": "b", "text": "Learning without labels"}],
             "correct_key": "a", "explanation": "Labels guide it.", "difficulty": 2},
            {"stem": "Which is a classifier?",
             "options": [{"key": "a", "text": "K-means"}, {"key": "b", "text": "Logistic regression"}],
             "correct_key": "b", "explanation": "Logistic regression classifies.", "difficulty": 2},
        ]
    })
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(responses=[canned])
    r = await api.post(
        "/assessments/generate", headers=h,
        json={"skill_slug": "machine-learning", "num_questions": 2, "difficulty": 2},
    )
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "llm"
    assert r.json()["question_count"] == 2


async def test_generate_falls_back_when_llm_output_invalid(api: AsyncClient) -> None:
    _, email = await _user()
    h = await _auth(api, email)
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(responses=["not json at all"])
    r = await api.post(
        "/assessments/generate", headers=h,
        json={"skill_slug": "statistics", "num_questions": 4, "difficulty": 2},
    )
    assert r.status_code == 201
    assert r.json()["source"] == "template"  # invalid LLM output -> deterministic fallback


# --- submit report ---------------------------------------------------------
async def test_submit_report_is_deterministic_and_maps_proficiency(api: AsyncClient) -> None:
    _, admin_email = await _user(UserRole.ADMIN)
    admin = await _auth(api, admin_email)
    learner_id, learner_email = await _user()
    learner = await _auth(api, learner_email)

    gen = await api.post(
        "/assessments/generate", headers=admin,
        json={"skill_slug": "statistics", "num_questions": 5, "difficulty": 2, "use_llm": False},
    )
    aid = gen.json()["assessment_id"]
    keyed = await _answer_key(api, admin, aid)

    # answer all correct -> 100% -> strong_mastery
    answers = [{"question_id": q["id"], "response": q["correct_answer"]["value"]} for q in keyed]
    r = await api.post(f"/assessments/{aid}/submit", headers=learner, json={"answers": answers})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["percentage"] == 1.0
    assert body["passed"] is True
    assert body["mastery_level"] == "strong_mastery"
    assert "Advance" in body["recommended_next_action"]
    # proficiency was updated deterministically for the assessed skill
    assert body["skill_updates"]
    assert body["skill_updates"][0]["new_proficiency"] > body["skill_updates"][0]["previous_proficiency"]
    assert body["weak_topics"] == []


async def test_submit_report_flags_weak_and_remediation(api: AsyncClient) -> None:
    _, admin_email = await _user(UserRole.ADMIN)
    admin = await _auth(api, admin_email)
    _, learner_email = await _user()
    learner = await _auth(api, learner_email)

    gen = await api.post(
        "/assessments/generate", headers=admin,
        json={"skill_slug": "deep-learning", "num_questions": 5, "difficulty": 2, "use_llm": False},
    )
    aid = gen.json()["assessment_id"]
    keyed = await _answer_key(api, admin, aid)
    # deliberately answer everything wrong -> 0% -> remediation, weak topic
    wrong = []
    for q in keyed:
        correct = q["correct_answer"]["value"]
        options = [o["key"] for o in q["options"]]
        wrong_key = next(k for k in options if k != correct)
        wrong.append({"question_id": q["id"], "response": wrong_key})
    r = await api.post(f"/assessments/{aid}/submit", headers=learner, json={"answers": wrong})
    body = r.json()
    assert body["percentage"] == 0.0
    assert body["mastery_level"] == "requires_remediation"
    assert "Remediate" in body["recommended_next_action"]
    assert body["weak_topics"]  # the assessed skill is weak


async def test_results_endpoint(api: AsyncClient) -> None:
    _, admin_email = await _user(UserRole.ADMIN)
    admin = await _auth(api, admin_email)
    _, learner_email = await _user()
    learner = await _auth(api, learner_email)
    gen = await api.post(
        "/assessments/generate", headers=admin,
        json={"skill_slug": "pytorch", "num_questions": 3, "difficulty": 2, "use_llm": False},
    )
    aid = gen.json()["assessment_id"]
    keyed = await _answer_key(api, admin, aid)
    answers = [{"question_id": q["id"], "response": q["correct_answer"]["value"]} for q in keyed]
    await api.post(f"/assessments/{aid}/submit", headers=learner, json={"answers": answers})

    r = await api.get(f"/assessments/{aid}/results", headers=learner)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["assessment_id"] == aid


async def test_generate_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/assessments/generate", json={"skill_slug": "python"})
    assert r.status_code == 401

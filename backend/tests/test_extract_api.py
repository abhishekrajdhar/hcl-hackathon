"""Integration tests for POST /api/profile/extract.

Run in-process against the seeded database; the LLM is a seeded MockProvider
injected via FastAPI dependency override, so no network or credentials are used.
"""

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

PW = "extract-pw-12345"
EXAMPLE = (
    "I am a second-year student. I know Python well and have built two machine "
    "learning projects using scikit-learn. I want to become a computer vision "
    "engineer. I can study around 10 hours per week."
)


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            return bool(await session.scalar(text("SELECT count(*) FROM skills")))
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


def _use_provider(provider: MockProvider) -> None:
    app.dependency_overrides[get_llm_provider_dep] = lambda: provider


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole = UserRole.LEARNER) -> uuid.UUID:
    email = f"{role.value}-ext-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        user = await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(PW), "role": role}
        )
        await session.commit()
        return user.id


async def _auth(api: AsyncClient, user_id: uuid.UUID) -> dict[str, str]:
    async with SessionLocal() as session:
        email = (await UserRepository(session).get(user_id)).email
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> tuple[uuid.UUID, dict[str, str]]:
    uid = await _make_user()
    return uid, await _auth(api, uid)


# --- happy path: the example message ---------------------------------------
async def test_extract_example_message(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    _use_provider(MockProvider())  # heuristic extraction
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract", headers=h, json={"user_id": str(uid), "message": EXAMPLE}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ext = body["extraction"]
        assert ext["experience_level"] == "intermediate"
        assert ext["target_role"] == "computer vision engineer"
        assert ext["weekly_hours"] == 10
        assert body["provider"] == "mock"
        assert body["applied"] is False  # not applied unless requested


# --- structured skills resolved against the catalogue ----------------------
async def test_extract_resolves_and_flags_unknown_skills(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    # A model output naming a real catalogue skill, a typo'd one, and a fake one.
    canned = json.dumps(
        {
            "target_role": "ML engineer",
            "skills": [
                {"name": "Python", "proficiency": 0.85},
                {"name": "Machnie Learning", "proficiency": 0.6},
                {"name": "Underwater Basket Weaving", "proficiency": 0.9},
            ],
        }
    )
    _use_provider(MockProvider(responses=[canned]))
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract", headers=h, json={"user_id": str(uid), "message": "..."}
        )
        assert resp.status_code == 200
        by_query = {r["query"]: r for r in resp.json()["resolved_skills"]}
        assert by_query["Python"]["status"] == "matched"
        assert by_query["Python"]["slug"] == "python"
        assert by_query["Machnie Learning"]["status"] == "matched"  # trigram
        assert by_query["Machnie Learning"]["slug"] == "machine-learning"
        # Hallucinated skill is reported, never matched.
        assert by_query["Underwater Basket Weaving"]["status"] == "unknown"
        assert any("not found in the catalogue" in w for w in resp.json()["warnings"])


# --- apply persists only catalogue-resolved skills -------------------------
async def test_extract_apply_persists_matched_skills_only(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    canned = json.dumps(
        {
            "experience_level": "intermediate",
            "goal": "Become a computer vision engineer",
            "target_role": "Computer Vision Engineer",
            "weekly_hours": 10,
            "timeline": "6 months",
            "skills": [
                {"name": "Python", "proficiency": 0.8},
                {"name": "Totally Fake Skill", "proficiency": 0.9},
            ],
        }
    )
    _use_provider(MockProvider(responses=[canned]))
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract",
            headers=h,
            json={"user_id": str(uid), "message": "...", "apply": True},
        )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        # Profile fields persisted.
        profile = await client.get(f"/profile/{uid}", headers=h)
        pdata = profile.json()["profile"]
        assert pdata["target_role"] == "Computer Vision Engineer"
        assert pdata["weekly_hours"] == 10
        assert pdata["target_deadline"] is not None  # "6 months" -> a date
        assert pdata["extraction_model"].startswith("mock:")

        # Only the real skill was written; the fake one was dropped.
        skills = {s["skill"]["slug"] for s in profile.json()["skills"]}
        assert "python" in skills
        assert profile.json()["skill_count"] == 1


# --- robustness: malformed output then repair ------------------------------
async def test_extract_recovers_from_malformed_then_valid(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    # First response is unparseable; the repair attempt returns valid JSON.
    provider = MockProvider(responses=["not json at all", json.dumps({"weekly_hours": 7})])
    _use_provider(provider)
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract", headers=h, json={"user_id": str(uid), "message": "..."}
        )
        assert resp.status_code == 200
        assert resp.json()["extraction"]["weekly_hours"] == 7


async def test_extract_fails_cleanly_when_output_never_valid(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    provider = MockProvider(responses=["garbage", "still garbage", "more garbage"])
    _use_provider(provider)
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract", headers=h, json={"user_id": str(uid), "message": "..."}
        )
        assert resp.status_code == 503
        assert resp.json()["code"] == "llm_output_invalid"


async def test_extract_flags_ambiguous_goal(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    _use_provider(MockProvider(responses=[json.dumps({"skills": []})]))
    async with _client() as client:
        h = await _auth(client, uid)
        resp = await client.post(
            "/profile/extract", headers=h, json={"user_id": str(uid), "message": "hi"}
        )
        assert resp.status_code == 200
        warnings = " ".join(resp.json()["warnings"]).lower()
        assert "goal" in warnings and "ambiguous" in warnings


# --- authorization ---------------------------------------------------------
async def test_extract_forbidden_for_other_user(api: AsyncClient) -> None:
    owner = await _make_user()
    other = await _make_user()
    _use_provider(MockProvider())
    async with _client() as client:
        other_h = await _auth(client, other)
        resp = await client.post(
            "/profile/extract",
            headers=other_h,
            json={"user_id": str(owner), "message": EXAMPLE},
        )
        assert resp.status_code == 403


def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test/api/v1")

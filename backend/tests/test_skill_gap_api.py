"""Integration tests for POST /api/skill-gap/analyze.

Run in-process against the seeded skill graph; skipped when no DB is reachable.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.repositories.user import UserRepository

pytestmark = pytest.mark.asyncio

PW = "gap-pw-12345"


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            return bool(await session.scalar(text("SELECT count(*) FROM prerequisites")))
    except Exception:
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_db() -> None:
    if not await _seeded():
        pytest.skip("database not reachable or not seeded", allow_module_level=True)


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole = UserRole.LEARNER) -> tuple[uuid.UUID, str]:
    email = f"{role.value}-gap-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        user = await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(PW), "role": role}
        )
        await session.commit()
        return user.id, email


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> tuple[uuid.UUID, dict[str, str]]:
    uid, email = await _make_user()
    return uid, await _auth(api, email)


def _positions(gaps: list[dict]) -> dict[str, int]:
    return {g["skill"]["slug"]: i for i, g in enumerate(gaps)}


# --- the task example, explicit skills -------------------------------------
async def test_analyze_explicit_ml_engineer(learner) -> None:  # type: ignore[no-untyped-def]
    uid, h = learner
    async with _client() as api:
        h = await _auth(api, (await _email_of(uid)))
        r = await api.post(
            "/skill-gap/analyze",
            headers=h,
            json={
                "target_skills": [
                    {"skill_slug": "python", "required_level": 0.8},
                    {"skill_slug": "statistics", "required_level": 0.7, "importance": 0.9},
                    {"skill_slug": "machine-learning", "required_level": 0.8},
                    {"skill_slug": "deep-learning", "required_level": 0.7, "importance": 0.8},
                    {"skill_slug": "pytorch", "required_level": 0.6, "importance": 0.6},
                    {"skill_slug": "mlops-fundamentals", "required_level": 0.5, "importance": 0.5},
                ],
                "current_skills": [
                    {"skill_slug": "python", "current_level": 0.9},
                    {"skill_slug": "statistics", "current_level": 0.4},
                    {"skill_slug": "machine-learning", "current_level": 0.3},
                    {"skill_slug": "deep-learning", "current_level": 0.1},
                ],
                "top_k": 5,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()

        # python is met -> excluded, listed under met_targets
        slugs = {g["skill"]["slug"] for g in body["gaps"]}
        assert "python" not in slugs
        assert "python" in {m["slug"] for m in body["met_targets"]}

        # each gap has the full contract
        item = body["gaps"][0]
        for field in ("skill", "current_level", "required_level", "gap", "prerequisites",
                      "priority", "reason", "is_target", "downstream_count"):
            assert field in item
        assert item["reason"]

        pos = _positions(body["gaps"])
        # prerequisite-aware ordering, NOT gap-desc
        assert pos["statistics"] < pos["machine-learning"]
        assert pos["machine-learning"] < pos["deep-learning"]
        # transitive prerequisites pulled in
        assert "neural-networks" in slugs
        # priority skills are learnable now
        assert body["priority_skills"]
        assert body["total_gaps"] == len(body["gaps"])


async def test_gap_equals_required_minus_current(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, await _email_of(uid))
        r = await api.post(
            "/skill-gap/analyze",
            headers=h,
            json={
                "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8}],
                "current_skills": [{"skill_slug": "machine-learning", "current_level": 0.3}],
            },
        )
        ml = next(g for g in r.json()["gaps"] if g["skill"]["slug"] == "machine-learning")
        assert abs(ml["gap"] - 0.5) < 1e-6
        assert ml["is_target"] is True


# --- current levels pulled from the learner's profile ----------------------
async def test_analyze_uses_user_profile_skills(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, await _email_of(uid))
        ml = await _skill_id(api, h, "machine-learning")
        # record a current proficiency on the learner's profile
        await api.post(
            f"/profile/{uid}/skills", headers=h, json={"skill_id": str(ml), "proficiency": 0.3}
        )
        r = await api.post(
            "/skill-gap/analyze",
            headers=h,
            json={
                "user_id": str(uid),
                "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8}],
            },
        )
        assert r.status_code == 200, r.text
        gap = next(g for g in r.json()["gaps"] if g["skill"]["slug"] == "machine-learning")
        assert abs(gap["current_level"] - 0.3) < 1e-6
        assert abs(gap["gap"] - 0.5) < 1e-6


# --- goal-derived required vector ------------------------------------------
async def test_analyze_from_goal(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, await _email_of(uid))
        ml = await _skill_id(api, h, "machine-learning")
        dl = await _skill_id(api, h, "deep-learning")
        goal = await api.post(
            "/goals",
            headers=h,
            json={
                "title": "Become an ML Engineer",
                "target_skills": [
                    {"skill_id": str(ml), "required_level": 8, "importance": 1.0},
                    {"skill_id": str(dl), "required_level": 7, "importance": 0.8},
                ],
            },
        )
        goal_id = goal.json()["id"]
        r = await api.post("/skill-gap/analyze", headers=h, json={"goal_id": goal_id})
        assert r.status_code == 200, r.text
        assert r.json()["goal_id"] == goal_id
        slugs = {g["skill"]["slug"] for g in r.json()["gaps"]}
        # required_level 8/10 -> 0.8; both targets should appear as gaps
        assert {"machine-learning", "deep-learning"} <= slugs


# --- validation & authorization --------------------------------------------
async def test_missing_required_source_rejected(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, await _email_of(uid))
        r = await api.post(
            "/skill-gap/analyze",
            headers=h,
            json={"current_skills": [{"skill_slug": "python", "current_level": 0.5}]},
        )
        assert r.status_code == 422  # no goal_id and no target_skills


async def test_unknown_skill_slug_404(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, await _email_of(uid))
        r = await api.post(
            "/skill-gap/analyze",
            headers=h,
            json={
                "target_skills": [{"skill_slug": "quantum-basket-weaving", "required_level": 0.8}],
                "current_skills": [{"skill_slug": "python", "current_level": 0.5}],
            },
        )
        assert r.status_code == 404


async def test_cannot_analyze_another_users_skills(api: AsyncClient) -> None:
    owner, _ = await _make_user()
    other_id, other_email = await _make_user()
    async with _client() as client:
        other_h = await _auth(client, other_email)
        r = await client.post(
            "/skill-gap/analyze",
            headers=other_h,
            json={
                "user_id": str(owner),
                "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8}],
            },
        )
        assert r.status_code == 403


async def test_requires_auth(api: AsyncClient) -> None:
    r = await api.post(
        "/skill-gap/analyze",
        json={"target_skills": [{"skill_slug": "python", "required_level": 0.8}]},
    )
    assert r.status_code == 401


# --- helpers ---------------------------------------------------------------
def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test/api/v1")


async def _email_of(user_id: uuid.UUID) -> str:
    async with SessionLocal() as session:
        return (await UserRepository(session).get(user_id)).email


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> uuid.UUID:
    r = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    for item in r.json()["items"]:
        if item["slug"] == slug:
            return uuid.UUID(item["id"])
    raise AssertionError(f"seed skill '{slug}' missing")

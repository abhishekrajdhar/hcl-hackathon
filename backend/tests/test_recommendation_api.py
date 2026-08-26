"""Integration tests for POST /api/recommendations (hybrid ranking engine).

Run in-process against the seeded catalogue; skipped when no DB is reachable.
Embeddings are the mock provider, so ranking is deterministic and offline.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.embeddings.factory import get_embedding_provider
from app.main import app
from app.models.enums import UserRole
from app.repositories.user import UserRepository
from app.services.embedding_service import EmbeddingService

pytestmark = pytest.mark.asyncio

PW = "rec-pw-12345"


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            return bool(await session.scalar(text("SELECT count(*) FROM resources")))
    except Exception:
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_db() -> None:
    if not await _seeded():
        pytest.skip("database not reachable or not seeded", allow_module_level=True)
    # ensure the catalogue is embedded so semantic recall works
    async with SessionLocal() as session:
        await EmbeddingService(session, get_embedding_provider()).embed_all(only_missing=True)


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole = UserRole.LEARNER) -> tuple[uuid.UUID, str]:
    email = f"{role.value}-rec-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        user = await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(PW), "role": role}
        )
        await session.commit()
        return user.id, email


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> str:
    r = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    for item in r.json()["items"]:
        if item["slug"] == slug:
            return item["id"]
    raise AssertionError(f"seed skill '{slug}' missing")


@pytest_asyncio.fixture
async def beginner(api: AsyncClient):  # type: ignore[no-untyped-def]
    """A learner who knows Python & Statistics but not ML/DL, with a profile."""
    uid, email = await _make_user()
    h = await _auth(api, email)
    await api.put(
        f"/profile/{uid}",
        headers=h,
        json={"target_role": "ML Engineer", "weekly_hours": 10,
              "preferred_modalities": ["video", "project"]},
    )
    py = await _skill_id(api, h, "python")
    stats = await _skill_id(api, h, "statistics")
    await api.post(f"/profile/{uid}/skills", headers=h, json={"skill_id": py, "proficiency": 0.85})
    await api.post(f"/profile/{uid}/skills", headers=h, json={"skill_id": stats, "proficiency": 0.5})
    return uid, h


def _ml_engineer_request(uid: uuid.UUID, **overrides) -> dict:
    body = {
        "user_id": str(uid),
        "target_skills": [
            {"skill_slug": "machine-learning", "required_level": 0.8},
            {"skill_slug": "deep-learning", "required_level": 0.7},
            {"skill_slug": "pytorch", "required_level": 0.6},
        ],
        "goal_text": "become a machine learning engineer",
        "top_k": 6,
    }
    body.update(overrides)
    return body


# --- core ranking behaviour ------------------------------------------------
async def test_recommendations_are_ready_and_scored(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    r = await api.post("/recommendations", headers=h, json=_ml_engineer_request(uid))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    assert body["count"] <= 6
    # every returned recommendation is something the learner can start now
    assert all(item["is_ready"] for item in body["recommendations"])
    # scores are in [0,1] and sorted descending
    scores = [item["score"] for item in body["recommendations"]]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    # advanced resources with unmet prerequisites were gated out
    assert body["excluded_unready"] >= 1
    # the default weights are surfaced for transparency
    assert body["weights"]["semantic_similarity"] == 0.30


async def test_each_item_has_scores_and_reason(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    r = await api.post("/recommendations", headers=h, json=_ml_engineer_request(uid))
    item = r.json()["recommendations"][0]
    for field in ("resource", "score", "rank", "is_ready", "factors", "contributions", "reason"):
        assert field in item
    # all seven+ hybrid factors are reported, each normalised
    for factor in ("semantic_similarity", "skill_gap_match", "prerequisite_match",
                   "difficulty_match", "preference_match", "quality_score", "historical_success"):
        assert 0.0 <= item["factors"][factor] <= 1.0
    assert item["reason"]


async def test_advanced_course_not_recommended_before_foundations(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    r = await api.post("/recommendations", headers=h, json=_ml_engineer_request(uid, top_k=10))
    titles = " ".join(i["resource"]["title"].lower() for i in r.json()["recommendations"])
    # the learner lacks linear-algebra, a prerequisite of the deep-learning and
    # CS231n courses, so those must not appear among the ready recommendations.
    assert "cs231" not in titles
    assert "deep learning specialization" not in titles


async def test_include_unready_surfaces_gated_resources(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    # Target the DEEP end of the graph on purpose. Retrieval returns a bounded
    # candidate pool, so a broad "ML engineer" goal can legitimately fill it
    # with beginner material the learner is ready for — which says nothing
    # about whether the gate works. Asking for neural networks guarantees the
    # pool contains resources whose prerequisites this learner has not met.
    r = await api.post(
        "/recommendations",
        headers=h,
        json={
            "user_id": str(uid),
            "target_skills": [
                {"skill_slug": "neural-networks", "required_level": 0.8},
                {"skill_slug": "deep-learning", "required_level": 0.8},
            ],
            # `skill_slug` narrows retrieval to resources for that skill.
            # Without it the candidate pool is bounded and can fill with
            # beginner material this learner IS ready for, which tells us
            # nothing about the gate — the pool, not the gate, would decide
            # the test.
            "skill_slug": "neural-networks",
            "goal_text": "deep learning and neural networks",
            "include_unready": True,
            "top_k": 40,
        },
    )
    body = r.json()
    unready = [i for i in body["recommendations"] if not i["is_ready"]]
    assert unready, "with include_unready, gated resources should appear"
    # every ready item precedes every unready item
    first_unready = next(i for i in body["recommendations"] if not i["is_ready"])["rank"]
    assert all(i["rank"] < first_unready for i in body["recommendations"] if i["is_ready"])
    # unready items explain what is missing
    assert any(i["unmet_prerequisites"] for i in unready)
    assert any("build" in i["reason"].lower() for i in unready)


async def test_optional_skill_focuses_results(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    r = await api.post(
        "/recommendations",
        headers=h,
        json={"user_id": str(uid), "skill_slug": "pytorch", "top_k": 5},
    )
    assert r.status_code == 200, r.text
    # every result teaches the requested skill
    for item in r.json()["recommendations"]:
        slugs = {s["skill"]["slug"] for s in item["resource"]["skills"]}
        assert "pytorch" in slugs


async def test_persist_stores_recommendations(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    gen = await api.post(
        "/recommendations", headers=h, json=_ml_engineer_request(uid, persist=True)
    )
    assert gen.status_code == 200
    stored = await api.get("/recommendations", headers=h)
    assert stored.json()["total"] == gen.json()["count"]
    top = stored.json()["items"][0]
    assert top["reason"]
    assert "factors" in top["rationale_trace"]


# --- validation & authorization --------------------------------------------
async def test_requires_a_goal(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, h = beginner
    r = await api.post("/recommendations", headers=h, json={"user_id": str(uid)})
    assert r.status_code == 422


async def test_cannot_recommend_for_another_user(api: AsyncClient) -> None:
    owner, _ = await _make_user()
    _, other_email = await _make_user()
    other_h = await _auth(api, other_email)
    r = await api.post(
        "/recommendations",
        headers=other_h,
        json={"user_id": str(owner), "skill_slug": "python"},
    )
    assert r.status_code == 403


async def test_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/recommendations", json={"user_id": str(uuid.uuid4()), "skill_slug": "python"})
    assert r.status_code == 401


async def test_admin_can_recommend_for_any_user(api: AsyncClient, beginner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = beginner
    _, admin_email = await _make_user(UserRole.ADMIN)
    admin_h = await _auth(api, admin_email)
    r = await api.post("/recommendations", headers=admin_h, json=_ml_engineer_request(uid))
    assert r.status_code == 200
    assert r.json()["user_id"] == str(uid)

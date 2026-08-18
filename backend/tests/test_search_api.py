"""Integration tests for embedding generation and semantic retrieval.

Run in-process against the seeded database; skipped when none is reachable.
The mock embedding provider makes cosine similarity reflect token overlap, so
retrieval assertions are meaningful without a neural model.
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

PW = "search-pw-12345"


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


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole = UserRole.LEARNER) -> tuple[uuid.UUID, str]:
    email = f"{role.value}-search-{uuid.uuid4().hex[:10]}@example.com"
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
async def admin(api: AsyncClient) -> dict[str, str]:
    _, email = await _make_user(UserRole.ADMIN)
    return await _auth(api, email)


@pytest_asyncio.fixture
async def learner_ctx(api: AsyncClient) -> tuple[uuid.UUID, dict[str, str]]:
    uid, email = await _make_user()
    return uid, await _auth(api, email)


async def _ensure_embedded(api: AsyncClient, admin: dict[str, str]) -> None:
    """Make sure the catalogue has embeddings (idempotent, only-missing)."""
    r = await api.post("/resources/embed-all", headers=admin, params={"only_missing": True})
    assert r.status_code == 200, r.text


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> str:
    r = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    for item in r.json()["items"]:
        if item["slug"] == slug:
            return item["id"]
    raise AssertionError(f"seed skill '{slug}' missing")


# --- embedding endpoints ---------------------------------------------------
async def test_embed_all_and_single(api: AsyncClient, admin) -> None:  # type: ignore[no-untyped-def]
    r = await api.post("/resources/embed-all", headers=admin, params={"only_missing": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["embedded"] >= 25
    assert body["dimension"] == 384
    assert body["provider"] == "mock"

    # single resource embed returns its canonical text
    listing = await api.get("/resources", headers=admin, params={"limit": 1})
    rid = listing.json()["items"][0]["id"]
    one = await api.post(f"/resources/{rid}/embed", headers=admin)
    assert one.status_code == 200
    assert one.json()["dimension"] == 384
    assert "Title:" in one.json()["canonical_text"]


async def test_embed_requires_admin(api: AsyncClient, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    _, learner = learner_ctx
    r = await api.post("/resources/embed-all", headers=learner)
    assert r.status_code == 403


# --- semantic search -------------------------------------------------------
async def test_semantic_search_ranks_relevant_first(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx

    r = await api.post(
        "/search/semantic",
        headers=learner,
        json={"query": "deep learning neural network course", "top_k": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    assert len(body["results"]) <= 5
    # similarity is sorted descending
    sims = [res["similarity"] for res in body["results"]]
    assert sims == sorted(sims, reverse=True)
    # the top hit is clearly a deep-learning resource
    top_title = body["results"][0]["resource"]["title"].lower()
    assert "deep learning" in top_title


async def test_semantic_search_respects_top_k(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx
    r = await api.post(
        "/search/semantic", headers=learner, json={"query": "machine learning", "top_k": 3}
    )
    assert len(r.json()["results"]) <= 3


async def test_semantic_search_with_type_filter(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx
    r = await api.post(
        "/search/semantic",
        headers=learner,
        json={"query": "machine learning", "top_k": 10, "resource_type": "project"},
    )
    assert r.status_code == 200
    assert all(res["resource"]["resource_type"] == "project" for res in r.json()["results"])


async def test_semantic_search_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/search/semantic", json={"query": "x", "top_k": 3})
    assert r.status_code == 401


async def test_empty_query_rejected(api: AsyncClient, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    _, learner = learner_ctx
    r = await api.post("/search/semantic", headers=learner, json={"query": "   ", "top_k": 3})
    # blank query fails validation (min_length) or the empty-query guard
    assert r.status_code in (422, 400)


# --- search_resources_for_* ------------------------------------------------
async def test_search_for_skill(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx
    pytorch = await _skill_id(api, learner, "pytorch")
    r = await api.get(f"/search/for-skill/{pytorch}", headers=learner, params={"top_k": 5})
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    titles = " ".join(res["resource"]["title"].lower() for res in r.json()["results"])
    assert "pytorch" in titles


async def test_search_for_skill_teaches_only(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx
    ml = await _skill_id(api, learner, "machine-learning")
    r = await api.get(
        f"/search/for-skill/{ml}", headers=learner, params={"teaches_only": True, "top_k": 20}
    )
    assert r.status_code == 200
    # Every result must structurally teach machine-learning.
    for res in r.json()["results"]:
        slugs = {s["skill"]["slug"] for s in res["resource"]["skills"]}
        assert "machine-learning" in slugs


async def test_search_for_goal(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    _, learner = learner_ctx
    r = await api.post(
        "/search/for-goal",
        headers=learner,
        json={"goal_text": "become a computer vision engineer", "top_k": 5},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    titles = " ".join(res["resource"]["title"].lower() for res in r.json()["results"])
    assert "vision" in titles or "detection" in titles


async def test_search_for_profile(api: AsyncClient, admin, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    await _ensure_embedded(api, admin)
    uid, learner = learner_ctx
    # Give the learner a profile expressing an NLP/LLM intent.
    await api.put(
        f"/profile/{uid}",
        headers=learner,
        json={
            "goal_text_raw": "learn to build large language model applications",
            "target_role": "LLM Engineer",
            "interests": ["llm", "transformers"],
        },
    )
    r = await api.get("/search/for-profile", headers=learner, params={"top_k": 5})
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    titles = " ".join(res["resource"]["title"].lower() for res in r.json()["results"])
    assert "llm" in titles or "language model" in titles or "retrieval" in titles


async def test_search_for_profile_without_profile_errors(api: AsyncClient, learner_ctx) -> None:  # type: ignore[no-untyped-def]
    _, learner = learner_ctx
    r = await api.get("/search/for-profile", headers=learner, params={"top_k": 5})
    assert r.status_code == 404

"""Integration tests for the learning-resource system.

Run in-process against the seeded database; skipped when none is reachable.
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

PW = "resource-pw-12345"


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


async def _make_user(role: UserRole = UserRole.LEARNER) -> str:
    email = f"{role.value}-res-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(PW), "role": role}
        )
        await session.commit()
    return email


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin(api: AsyncClient) -> dict[str, str]:
    return await _auth(api, await _make_user(UserRole.ADMIN))


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> dict[str, str]:
    return await _auth(api, await _make_user())


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> str:
    r = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    for item in r.json()["items"]:
        if item["slug"] == slug:
            return item["id"]
    raise AssertionError(f"seed skill '{slug}' missing")


# --- CRUD ------------------------------------------------------------------
async def test_create_get_update_delete(api: AsyncClient, admin, learner) -> None:  # type: ignore[no-untyped-def]
    py = await _skill_id(api, admin, "python")
    ml = await _skill_id(api, admin, "machine-learning")

    created = await api.post(
        "/resources",
        headers=admin,
        json={
            "provider": "TestProvider",
            "external_id": f"ext-{uuid.uuid4().hex[:8]}",
            "title": "Intro to ML",
            "description": "A test course",
            "url": "https://example.com/intro-ml",
            "resource_type": "course",
            "difficulty": 3,
            "estimated_hours": 12.5,
            "quality_score": 0.8,
            "rating": 4.5,
            "metadata": {"language_note": "en-US"},
            "skills": [{"skill_id": ml, "teaches_level_from": 0, "teaches_level_to": 0.6, "is_primary": True}],
            "prerequisites": [{"skill_id": py, "min_proficiency": 0.4}],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["resource_type"] == "course"
    assert body["estimated_hours"] == 12.5
    assert body["quality_score"] == 0.8
    # `metadata` is the API name for the ORM `extra` field.
    assert body["metadata"] == {"language_note": "en-US"}
    assert "extra" not in body
    assert len(body["skills"]) == 1 and body["skills"][0]["skill"]["slug"] == "machine-learning"
    assert len(body["prerequisites"]) == 1 and body["prerequisites"][0]["min_proficiency"] == 0.4
    rid = body["id"]

    # GET (learner can read)
    got = await api.get(f"/resources/{rid}", headers=learner)
    assert got.status_code == 200 and got.json()["title"] == "Intro to ML"

    # PUT updates scalars and replaces collections
    updated = await api.put(
        f"/resources/{rid}",
        headers=admin,
        json={"estimated_hours": 20.0, "difficulty": 4, "prerequisites": []},
    )
    assert updated.status_code == 200
    assert updated.json()["estimated_hours"] == 20.0
    assert updated.json()["difficulty"] == 4
    assert updated.json()["prerequisites"] == []  # replaced with empty

    # DELETE
    assert (await api.delete(f"/resources/{rid}", headers=admin)).status_code == 204
    assert (await api.get(f"/resources/{rid}", headers=learner)).status_code == 404


async def test_create_requires_admin(api: AsyncClient, learner) -> None:  # type: ignore[no-untyped-def]
    r = await api.post(
        "/resources",
        headers=learner,
        json={"provider": "x", "title": "t", "url": "https://x.test"},
    )
    assert r.status_code == 403


async def test_invalid_level_band_rejected(api: AsyncClient, admin) -> None:  # type: ignore[no-untyped-def]
    ml = await _skill_id(api, admin, "machine-learning")
    r = await api.post(
        "/resources",
        headers=admin,
        json={
            "provider": "x",
            "title": "bad",
            "url": "https://x.test",
            "skills": [{"skill_id": ml, "teaches_level_from": 0.6, "teaches_level_to": 0.2}],
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_level_band"


async def test_quality_score_out_of_range_rejected(api: AsyncClient, admin) -> None:  # type: ignore[no-untyped-def]
    r = await api.post(
        "/resources",
        headers=admin,
        json={"provider": "x", "title": "t", "url": "https://x.test", "quality_score": 1.5},
    )
    assert r.status_code == 422


# --- filtering -------------------------------------------------------------
async def test_filter_by_skill(api: AsyncClient, admin, learner) -> None:  # type: ignore[no-untyped-def]
    pytorch = await _skill_id(api, admin, "pytorch")
    r = await api.get("/resources", headers=learner, params={"skill_id": pytorch, "limit": 100})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    # Every returned resource teaches pytorch.
    for item in r.json()["items"]:
        slugs = {s["skill"]["slug"] for s in item["skills"]}
        assert "pytorch" in slugs


async def test_filter_by_resource_type(api: AsyncClient, learner) -> None:  # type: ignore[no-untyped-def]
    r = await api.get("/resources", headers=learner, params={"resource_type": "project", "limit": 100})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    assert all(i["resource_type"] == "project" for i in r.json()["items"])


async def test_filter_by_difficulty(api: AsyncClient, learner) -> None:  # type: ignore[no-untyped-def]
    r = await api.get("/resources", headers=learner, params={"max_difficulty": 2, "limit": 100})
    assert r.status_code == 200
    assert all(i["difficulty"] <= 2 for i in r.json()["items"])

    exact = await api.get("/resources", headers=learner, params={"difficulty": 5, "limit": 100})
    assert all(i["difficulty"] == 5 for i in exact.json()["items"])


async def test_filter_by_estimated_duration(api: AsyncClient, learner) -> None:  # type: ignore[no-untyped-def]
    r = await api.get("/resources", headers=learner, params={"max_hours": 2, "limit": 100})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    assert all(i["estimated_hours"] <= 2 for i in r.json()["items"])

    long = await api.get("/resources", headers=learner, params={"min_hours": 50, "limit": 100})
    assert all(i["estimated_hours"] >= 50 for i in long.json()["items"])


async def test_combined_filters(api: AsyncClient, admin, learner) -> None:  # type: ignore[no-untyped-def]
    ml = await _skill_id(api, admin, "machine-learning")
    r = await api.get(
        "/resources",
        headers=learner,
        params={"skill_id": ml, "resource_type": "project", "limit": 100},
    )
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["resource_type"] == "project"
        assert "machine-learning" in {s["skill"]["slug"] for s in item["skills"]}


# --- prerequisites management ----------------------------------------------
async def test_prerequisite_endpoints(api: AsyncClient, admin) -> None:  # type: ignore[no-untyped-def]
    py = await _skill_id(api, admin, "python")
    stats = await _skill_id(api, admin, "statistics")
    created = await api.post(
        "/resources",
        headers=admin,
        json={"provider": "x", "title": "prereq test", "url": "https://x.test",
              "external_id": f"pre-{uuid.uuid4().hex[:8]}"},
    )
    rid = created.json()["id"]

    add = await api.post(
        f"/resources/{rid}/prerequisites", headers=admin,
        json={"skill_id": py, "min_proficiency": 0.5},
    )
    assert add.status_code == 201 and add.json()["skill"]["slug"] == "python"

    # duplicate → 409
    dup = await api.post(
        f"/resources/{rid}/prerequisites", headers=admin, json={"skill_id": py, "min_proficiency": 0.3}
    )
    assert dup.status_code == 409

    await api.post(
        f"/resources/{rid}/prerequisites", headers=admin, json={"skill_id": stats, "min_proficiency": 0.2}
    )
    lst = await api.get(f"/resources/{rid}/prerequisites", headers=admin)
    assert {p["skill"]["slug"] for p in lst.json()} == {"python", "statistics"}

    # remove one
    assert (await api.delete(f"/resources/{rid}/prerequisites/{py}", headers=admin)).status_code == 204
    lst2 = await api.get(f"/resources/{rid}/prerequisites", headers=admin)
    assert {p["skill"]["slug"] for p in lst2.json()} == {"statistics"}


# --- seeded catalogue ------------------------------------------------------
async def test_seeded_catalogue_has_all_types(api: AsyncClient, learner) -> None:  # type: ignore[no-untyped-def]
    types_present = set()
    for rtype in ("course", "project", "assessment", "documentation", "book", "tutorial", "article"):
        r = await api.get("/resources", headers=learner, params={"resource_type": rtype, "limit": 1})
        if r.json()["total"] > 0:
            types_present.add(rtype)
    # The seed must cover the headline course/project/assessment trio at least.
    assert {"course", "project", "assessment"} <= types_present

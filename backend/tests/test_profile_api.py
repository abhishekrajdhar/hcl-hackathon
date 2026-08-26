"""Integration tests for the Learner Profile Engine API.

Run in-process against the real (seeded) database; skip when none is reachable.
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

PW = "profile-pw-12345"


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


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole = UserRole.LEARNER) -> uuid.UUID:
    email = f"{role.value}-prof-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        user = await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(PW), "role": role}
        )
        await session.commit()
        return user.id


async def _auth(api: AsyncClient, user_id: uuid.UUID) -> dict[str, str]:
    async with SessionLocal() as session:
        user = await UserRepository(session).get(user_id)
        email = user.email
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> tuple[uuid.UUID, dict[str, str]]:
    uid = await _make_user()
    return uid, await _auth(api, uid)


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> uuid.UUID:
    r = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    for item in r.json()["items"]:
        if item["slug"] == slug:
            return uuid.UUID(item["id"])
    raise AssertionError(f"seed skill '{slug}' missing")


# --- PUT /profile/{user_id} + GET aggregate --------------------------------
async def test_put_and_get_full_profile(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    payload = {
        "goal_text_raw": "Become an ML engineer",
        "target_role": "Machine Learning Engineer",
        "experience_level": "intermediate",
        "weekly_hours": 12,
        "target_deadline": "2027-01-01",
        "preferred_modalities": ["video", "project"],
        "interests": ["nlp", "mlops"],
        "completed_courses": [{"title": "Intro to Python", "provider": "Coursera"}],
        "completed_projects": [{"title": "Spam classifier"}],
        "learning_preferences": {"pace": "steady"},
    }
    async with _client() as api:
        h = await _auth(api, uid)
        put = await api.put(f"/profile/{uid}", headers=h, json=payload)
        assert put.status_code == 200, put.text
        assert put.json()["target_role"] == "Machine Learning Engineer"

        got = await api.get(f"/profile/{uid}", headers=h)
        assert got.status_code == 200
        body = got.json()
        assert body["profile"]["goal_text_raw"] == "Become an ML engineer"
        assert body["profile"]["completed_courses"][0]["title"] == "Intro to Python"
        assert body["profile"]["interests"] == ["nlp", "mlops"]
        assert body["skill_count"] == 0
        assert body["assessment_history"]["total_attempts"] == 0


# --- skill proficiency 0..1 ------------------------------------------------
async def test_skill_proficiency_crud_in_unit_interval(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, uid)
        py = await _skill_id(api, h, "python")
        stats = await _skill_id(api, h, "statistics")

        # POST add
        r = await api.post(
            f"/profile/{uid}/skills", headers=h, json={"skill_id": str(py), "proficiency": 0.85}
        )
        assert r.status_code == 201, r.text
        assert r.json()["proficiency"] == 0.85
        assert r.json()["evidence_source"] == "self_report"
        assert r.json()["skill"]["slug"] == "python"

        # duplicate POST → 409
        dup = await api.post(
            f"/profile/{uid}/skills", headers=h, json={"skill_id": str(py), "proficiency": 0.5}
        )
        assert dup.status_code == 409

        # out-of-range → 422
        bad = await api.post(
            f"/profile/{uid}/skills", headers=h, json={"skill_id": str(stats), "proficiency": 1.4}
        )
        assert bad.status_code == 422

        # PUT create-or-replace
        put = await api.put(
            f"/profile/{uid}/skills/{stats}", headers=h, json={"proficiency": 0.45}
        )
        assert put.status_code == 200
        assert put.json()["proficiency"] == 0.45

        # PUT update existing
        put2 = await api.put(
            f"/profile/{uid}/skills/{py}", headers=h, json={"proficiency": 0.6}
        )
        assert put2.json()["proficiency"] == 0.6

        # GET list sorted by proficiency desc
        lst = await api.get(f"/profile/{uid}/skills", headers=h)
        profs = [s["proficiency"] for s in lst.json()]
        assert profs == sorted(profs, reverse=True)
        assert all(0.0 <= p <= 1.0 for p in profs)


async def test_current_level_synced_from_proficiency(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, uid)
        py = await _skill_id(api, h, "python")
        await api.post(
            f"/profile/{uid}/skills", headers=h, json={"skill_id": str(py), "proficiency": 0.8}
        )
        # The 0..10 mirror used by the graph engines must track proficiency.
        async with SessionLocal() as session:
            level = await session.scalar(
                text(
                    "SELECT current_level FROM user_skills "
                    "WHERE user_id = :u AND skill_id = :s"
                ),
                {"u": str(uid), "s": str(py)},
            )
        # python level_scale is 5 → 0.8 * 5 = 4.0
        assert level == pytest.approx(4.0)


# --- validation ------------------------------------------------------------
async def test_profile_validation_endpoint(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, uid)
        await api.put(
            f"/profile/{uid}",
            headers=h,
            json={"weekly_hours": 0, "target_deadline": "2020-01-01"},
        )
        r = await api.get(f"/profile/{uid}/validate", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["is_valid"] is False
        assert any(e["code"] == "deadline_in_past" for e in body["errors"])
        assert any(w["code"] == "weekly_hours_too_low" for w in body["warnings"])


# --- assessment → proficiency update ---------------------------------------
async def test_assessment_updates_proficiency(api: AsyncClient) -> None:
    admin_id = await _make_user(UserRole.ADMIN)
    learner_id = await _make_user()
    async with _client() as client:
        admin = await _auth(client, admin_id)
        learner = await _auth(client, learner_id)

        stats = await _skill_id(client, admin, "statistics")

        # Learner starts with a modest self-reported proficiency.
        await client.post(
            f"/profile/{learner_id}/skills",
            headers=learner,
            json={"skill_id": str(stats), "proficiency": 0.3},
        )

        # Admin builds a statistics assessment (all questions tagged to it).
        created = await client.post(
            "/assessments",
            headers=admin,
            json={
                "skill_id": str(stats),
                "title": "Statistics checkpoint",
                "passing_score": 0.6,
                "questions": [
                    {
                        "order_index": i,
                        "question_type": "single_choice",
                        "stem": f"Q{i}",
                        "options": [{"key": "a"}, {"key": "b"}],
                        "correct_answer": {"value": "a"},
                        "points": 1,
                        "skill_id": str(stats),
                    }
                    for i in range(6)
                ],
            },
        )
        assert created.status_code == 201, created.text
        assessment_id = created.json()["id"]
        keyed = await client.get(f"/assessments/{assessment_id}/questions", headers=admin)
        qids = [q["id"] for q in sorted(keyed.json(), key=lambda q: q["order_index"])]

        # Learner aces it.
        submit = await client.post(
            f"/assessments/{assessment_id}/submit",
            headers=learner,
            json={"answers": [{"question_id": q, "response": "a"} for q in qids]},
        )
        assert submit.status_code == 201, submit.text
        assert submit.json()["passed"] is True

        # Proficiency moved up from 0.3 toward 1.0, and evidence is now assessment.
        after = await client.get(f"/profile/{learner_id}/skills/{stats}", headers=learner)
        assert after.status_code == 200
        assert after.json()["proficiency"] > 0.3
        assert after.json()["evidence_source"] == "assessment"

        # A failing attempt pulls it back down.
        before_fail = after.json()["proficiency"]
        fail = await client.post(
            f"/assessments/{assessment_id}/submit",
            headers=learner,
            json={"answers": [{"question_id": q, "response": "b"} for q in qids]},
        )
        assert fail.json()["passed"] is False
        after_fail = await client.get(
            f"/profile/{learner_id}/skills/{stats}", headers=learner
        )
        assert after_fail.json()["proficiency"] < before_fail


async def test_assessment_creates_missing_skill_proficiency(api: AsyncClient) -> None:
    admin_id = await _make_user(UserRole.ADMIN)
    learner_id = await _make_user()
    async with _client() as client:
        admin = await _auth(client, admin_id)
        learner = await _auth(client, learner_id)
        prob = await _skill_id(client, admin, "probability")

        created = await client.post(
            "/assessments",
            headers=admin,
            json={
                "skill_id": str(prob),
                "title": "Probability diagnostic",
                "questions": [
                    {
                        "order_index": 0,
                        "question_type": "single_choice",
                        "stem": "Q",
                        "options": [{"key": "a"}, {"key": "b"}],
                        "correct_answer": {"value": "a"},
                        "points": 1,
                        "skill_id": str(prob),
                    }
                ],
            },
        )
        aid = created.json()["id"]
        keyed = await client.get(f"/assessments/{aid}/questions", headers=admin)
        qid = keyed.json()[0]["id"]

        # Learner has no probability skill yet.
        missing = await client.get(f"/profile/{learner_id}/skills/{prob}", headers=learner)
        assert missing.status_code == 404

        await client.post(
            f"/assessments/{aid}/submit",
            headers=learner,
            json={"answers": [{"question_id": qid, "response": "a"}]},
        )
        # It is now created from the assessment evidence.
        now = await client.get(f"/profile/{learner_id}/skills/{prob}", headers=learner)
        assert now.status_code == 200
        assert now.json()["proficiency"] > 0.0
        assert now.json()["evidence_source"] == "assessment"


# --- ingestion (LLM abstraction) -------------------------------------------
async def test_ingest_draft_preview_and_apply(learner) -> None:  # type: ignore[no-untyped-def]
    uid, _ = learner
    async with _client() as api:
        h = await _auth(api, uid)
        # Preview only (apply=false) does not persist.
        preview = await api.post(
            f"/profile/{uid}/ingest",
            headers=h,
            json={"text": "I can study 10 hours per week and prefer video and projects"},
        )
        assert preview.status_code == 200
        assert preview.json()["applied"] is False
        assert preview.json()["draft"]["weekly_hours"] == 10

        # Apply persists the draft into the profile.
        applied = await api.post(
            f"/profile/{uid}/ingest",
            headers=h,
            json={
                "text": "I can study 10 hours per week and prefer video and projects",
                "apply": True,
            },
        )
        assert applied.status_code == 200
        assert applied.json()["applied"] is True

        got = await api.get(f"/profile/{uid}", headers=h)
        assert got.json()["profile"]["weekly_hours"] == 10
        assert set(got.json()["profile"]["preferred_modalities"]) == {"video", "project"}
        assert got.json()["profile"]["extraction_model"] == "deterministic-v2"


# --- authorization ---------------------------------------------------------
async def test_learner_cannot_touch_another_users_profile(api: AsyncClient) -> None:
    owner = await _make_user()
    other = await _make_user()
    async with _client() as client:
        owner_h = await _auth(client, owner)
        other_h = await _auth(client, other)

        await client.put(f"/profile/{owner}", headers=owner_h, json={"weekly_hours": 5})

        forbidden = await client.get(f"/profile/{owner}", headers=other_h)
        assert forbidden.status_code == 403

        forbidden_write = await client.post(
            f"/profile/{owner}/skills",
            headers=other_h,
            json={"skill_id": str(uuid.uuid4()), "proficiency": 0.5},
        )
        assert forbidden_write.status_code == 403


async def test_admin_can_read_any_profile(api: AsyncClient) -> None:
    admin_id = await _make_user(UserRole.ADMIN)
    learner_id = await _make_user()
    async with _client() as client:
        admin = await _auth(client, admin_id)
        learner = await _auth(client, learner_id)
        await client.put(f"/profile/{learner_id}", headers=learner, json={"weekly_hours": 7})

        got = await client.get(f"/profile/{learner_id}", headers=admin)
        assert got.status_code == 200
        assert got.json()["profile"]["weekly_hours"] == 7


# --- helpers to open a client inside a test --------------------------------
def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test/api/v1")


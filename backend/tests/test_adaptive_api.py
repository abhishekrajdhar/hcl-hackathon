"""Integration tests for POST /api/adaptive/update (the adaptive pipeline)."""

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
from app.models.skill import UserSkill
from app.repositories.skill import SkillRepository
from app.repositories.user import LearnerProfileRepository, UserRepository

pytestmark = pytest.mark.asyncio
PW = "adaptive-pw-12345"


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


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as c:
        yield c


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _learner_with_path(api: AsyncClient, *, stat: float = 0.5) -> tuple[uuid.UUID, dict]:
    email = f"adapt-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        user = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW)})
        await s.flush()
        await LearnerProfileRepository(s).create({"user_id": user.id, "weekly_hours": 10})
        skills = SkillRepository(s)
        for slug, prof in [("python", 0.85), ("statistics", stat)]:
            sk = await skills.get_by_slug(slug)
            s.add(UserSkill(user_id=user.id, skill_id=sk.id, proficiency=prof,
                            current_level=prof * sk.level_scale, confidence=0.7))
        await s.commit()
        uid = user.id
    h = await _auth(api, email)
    # generate an active path
    await api.post("/learning-path/generate", headers=h, json={
        "user_id": str(uid),
        "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8},
                          {"skill_slug": "deep-learning", "required_level": 0.7}],
        "goal_text": "ML engineer",
    })
    return uid, h


async def test_explicit_score_applies_mvp_formula(api: AsyncClient) -> None:
    uid, h = await _learner_with_path(api, stat=0.5)
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid),
        "skill_scores": [{"skill_slug": "statistics", "score": 0.9}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trigger"] == "explicit"
    upd = body["updated_skills"][0]
    # 0.6*0.5 + 0.4*0.9 = 0.66
    assert abs(upd["new_proficiency"] - 0.66) < 1e-4
    assert abs(upd["previous_proficiency"] - 0.5) < 1e-4
    # score 0.9 > 0.85 unlocks the next milestone
    assert body["unlocked_milestones"]
    assert "unlocked" in body["next_recommended_action"].lower()


async def test_low_score_inserts_remediation(api: AsyncClient) -> None:
    uid, h = await _learner_with_path(api)
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid),
        "skill_scores": [{"skill_slug": "machine-learning", "score": 0.3}],
    })
    body = r.json()
    # score < 0.5 -> remediation inserted, remedial band
    assert body["updated_skills"][0]["level_band"] == "remedial"
    assert body["newly_recommended_resources"]
    assert "remediation" in body["next_recommended_action"].lower()


async def test_high_skill_reaches_advanced_and_skips_or_completes(api: AsyncClient) -> None:
    # machine-learning is a gap (required 0.8 > current 0.75), so it IS a path
    # milestone. A top score pushes it into the advanced band.
    email = f"adv-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        user = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW)})
        await s.flush()
        await LearnerProfileRepository(s).create({"user_id": user.id, "weekly_hours": 10})
        skills = SkillRepository(s)
        for slug, prof in [("python", 0.85), ("statistics", 0.85), ("machine-learning", 0.75)]:
            sk = await skills.get_by_slug(slug)
            s.add(UserSkill(user_id=user.id, skill_id=sk.id, proficiency=prof,
                            current_level=prof * sk.level_scale, confidence=0.7))
        await s.commit()
        uid = user.id
    h = await _auth(api, email)
    await api.post("/learning-path/generate", headers=h, json={
        "user_id": str(uid),
        "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8},
                          {"skill_slug": "deep-learning", "required_level": 0.7}],
        "goal_text": "ML engineer",
    })
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid), "skill_scores": [{"skill_slug": "machine-learning", "score": 1.0}],
    })
    body = r.json()
    # 0.6*0.75 + 0.4*1.0 = 0.85 -> advanced band (> 0.80)
    assert body["updated_skills"][0]["level_band"] == "advanced"
    # advanced learner: introductory ML resources skipped, or the milestone done
    assert body["removed_resources"] or body["completed_milestones"] or body["unlocked_milestones"]


async def test_completed_resource_updates_and_marks_item(api: AsyncClient) -> None:
    uid, h = await _learner_with_path(api)
    # find a resource in the active path
    path = await api.get(f"/learning-path/{uid}", headers=h)
    res_id = None
    for phase in path.json()["phases"]:
        for m in phase["milestones"]:
            for r in m["resources"]:
                if r.get("resource_id"):
                    res_id = r["resource_id"]
                    break
            if res_id:
                break
        if res_id:
            break
    assert res_id
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid), "completed_resource_id": res_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["trigger"] == "resource_completed"
    # proficiency was nudged for the resource's taught skills
    assert r.json()["updated_skills"]


async def test_skipped_resource_marks_removed(api: AsyncClient) -> None:
    uid, h = await _learner_with_path(api)
    path = await api.get(f"/learning-path/{uid}", headers=h)
    res_id = next(
        r["resource_id"]
        for phase in path.json()["phases"] for m in phase["milestones"]
        for r in m["resources"] if r.get("resource_id")
    )
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid), "skipped_resource_id": res_id,
    })
    assert r.status_code == 200
    assert r.json()["trigger"] == "resource_skipped"
    assert any(x["resource_id"] == res_id for x in r.json()["removed_resources"])


async def test_assessment_trigger_recovers_previous_no_double_apply(api: AsyncClient) -> None:
    email = f"adapt-as-{uuid.uuid4().hex[:10]}@example.com"
    admin_email = f"admin-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        learner = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW)})
        admin = await UserRepository(s).create({"email": admin_email, "hashed_password": hash_password(PW), "role": UserRole.ADMIN})
        await s.flush()
        sk = await SkillRepository(s).get_by_slug("statistics")
        s.add(UserSkill(user_id=learner.id, skill_id=sk.id, proficiency=0.5,
                        current_level=0.5 * sk.level_scale, confidence=0.7))
        await s.commit()
        uid = learner.id
    h = await _auth(api, email)
    admin_h = await _auth(api, admin_email)

    gen = await api.post("/assessments/generate", headers=admin_h,
                         json={"skill_slug": "statistics", "num_questions": 5, "use_llm": False})
    aid = gen.json()["assessment_id"]
    keyed = sorted((await api.get(f"/assessments/{aid}/questions", headers=admin_h)).json(),
                   key=lambda q: q["order_index"])
    ans = [{"question_id": q["id"], "response": q["correct_answer"]["value"]} for q in keyed]
    sub = await api.post(f"/assessments/{aid}/submit", headers=h, json={"answers": ans})
    result_id = sub.json()["result"]["id"]
    # submit already applied 0.6*0.5 + 0.4*1.0 = 0.7
    assert abs(sub.json()["skill_updates"][0]["new_proficiency"] - 0.7) < 1e-4

    r = await api.post("/adaptive/update", headers=h,
                       json={"user_id": str(uid), "assessment_result_id": result_id})
    body = r.json()
    assert body["trigger"] == "assessment"
    upd = body["updated_skills"][0]
    # recovered previous ~0.5, current 0.7 — NOT re-applied (would be 0.82)
    assert abs(upd["previous_proficiency"] - 0.5) < 0.02
    assert abs(upd["new_proficiency"] - 0.7) < 0.02
    # confirm the stored proficiency is still 0.7 (not double-applied)
    after = await api.get(f"/profile/{uid}/skills/{keyed[0]['skill_id']}", headers=h)
    assert abs(after.json()["proficiency"] - 0.7) < 1e-4


async def test_validation_requires_exactly_one_trigger(api: AsyncClient) -> None:
    uid, h = await _learner_with_path(api)
    # zero triggers
    assert (await api.post("/adaptive/update", headers=h, json={"user_id": str(uid)})).status_code == 422
    # two triggers
    r = await api.post("/adaptive/update", headers=h, json={
        "user_id": str(uid),
        "skill_scores": [{"skill_slug": "statistics", "score": 0.9}],
        "skipped_resource_id": str(uuid.uuid4()),
    })
    assert r.status_code == 422


async def test_cannot_adapt_another_users_path(api: AsyncClient) -> None:
    owner, _ = await _learner_with_path(api)
    other_email = f"other-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        await UserRepository(s).create({"email": other_email, "hashed_password": hash_password(PW)})
        await s.commit()
    other_h = await _auth(api, other_email)
    r = await api.post("/adaptive/update", headers=other_h, json={
        "user_id": str(owner), "skill_scores": [{"skill_slug": "statistics", "score": 0.9}],
    })
    assert r.status_code == 403


async def test_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/adaptive/update", json={
        "user_id": str(uuid.uuid4()), "skill_scores": [{"skill_slug": "python", "score": 0.9}],
    })
    assert r.status_code == 401

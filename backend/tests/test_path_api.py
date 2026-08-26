"""Integration tests for the learning-path generator API."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.skill import UserSkill
from app.repositories.skill import SkillRepository
from app.repositories.user import LearnerProfileRepository, UserRepository

pytestmark = pytest.mark.asyncio
PW = "path-pw-12345"


async def _seeded() -> bool:
    try:
        async with SessionLocal() as s:
            return bool(await s.scalar(text("SELECT count(*) FROM prerequisites")))
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


async def _learner_with_skills() -> tuple[uuid.UUID, str]:
    email = f"learner-path-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        user = await UserRepository(s).create(
            {"email": email, "hashed_password": hash_password(PW)}
        )
        await s.flush()
        await LearnerProfileRepository(s).create(
            {"user_id": user.id, "weekly_hours": 10, "preferred_modalities": ["video"],
             "target_role": "Computer Vision Engineer"}
        )
        skills = SkillRepository(s)
        for slug, prof in [("python", 0.85), ("statistics", 0.5)]:
            sk = await skills.get_by_slug(slug)
            s.add(UserSkill(user_id=user.id, skill_id=sk.id, proficiency=prof,
                            current_level=prof * sk.level_scale, confidence=0.7))
        await s.commit()
        return user.id, email


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _request(uid: uuid.UUID) -> dict:
    return {
        "user_id": str(uid),
        "target_skills": [
            {"skill_slug": "machine-learning", "required_level": 0.8},
            {"skill_slug": "deep-learning", "required_level": 0.7},
            {"skill_slug": "computer-vision", "required_level": 0.7},
        ],
        "goal_text": "become a computer vision engineer",
    }


def _order(roadmap: dict) -> list[str]:
    return [m["skill_slug"] for p in roadmap["phases"] for m in p["milestones"] if m["skill_slug"]]


async def test_generate_produces_ordered_roadmap(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    r = await api.post("/learning-path/generate", headers=h, json=_request(uid))
    assert r.status_code == 201, r.text
    body = r.json()

    # phase/milestone/roadmap contract
    assert body["phases"]
    assert body["phases"][0]["title"] == "Foundations"
    assert body["phases"][-1]["is_capstone"] is True
    milestone = body["phases"][0]["milestones"][0]
    for field in ("title", "current_level", "required_level", "gap", "prerequisites",
                  "completion_criteria", "resources"):
        assert field in milestone
    assert body["total_estimated_minutes"] > 0

    # PREREQUISITE ORDERING — the core guarantee
    order = _order(body)
    pos = {s: i for i, s in enumerate(order)}
    for dep, pre in [("machine-learning", "statistics"),
                     ("neural-networks", "machine-learning"),
                     ("deep-learning", "neural-networks"),
                     ("cnn", "deep-learning"),
                     ("computer-vision", "cnn")]:
        if dep in pos and pre in pos:
            assert pos[pre] < pos[dep], f"{pre} must precede {dep}"


async def test_prerequisites_appear_before_their_skill_in_every_phase(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    body = (await api.post("/learning-path/generate", headers=h, json=_request(uid))).json()
    order = _order(body)
    pos = {s: i for i, s in enumerate(order)}
    # each milestone's listed prerequisites (by name) that are also milestones
    # must come earlier
    name_to_slug = {m["title"]: m["skill_slug"] for p in body["phases"] for m in p["milestones"]}
    for phase in body["phases"]:
        for m in phase["milestones"]:
            if not m["skill_slug"]:
                continue
            for prereq_name in m["prerequisites"]:
                pslug = name_to_slug.get(prereq_name)
                if pslug and pslug in pos:
                    assert pos[pslug] < pos[m["skill_slug"]]


async def test_generate_from_goal(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    ml = None
    stats = None
    listing = await api.get("/skills", headers=h, params={"search": "machine-learning", "limit": 50})
    for it in listing.json()["items"]:
        if it["slug"] == "machine-learning":
            ml = it["id"]
    goal = await api.post(
        "/goals", headers=h,
        json={"title": "ML Engineer", "target_skills": [{"skill_id": ml, "required_level": 8}]},
    )
    r = await api.post(
        "/learning-path/generate", headers=h,
        json={"user_id": str(uid), "goal_id": goal.json()["id"], "goal_text": "ML engineer"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["goal_id"] == goal.json()["id"]


async def test_get_active_roadmap(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    gen = await api.post("/learning-path/generate", headers=h, json=_request(uid))
    got = await api.get(f"/learning-path/{uid}", headers=h)
    assert got.status_code == 200
    assert got.json()["path_id"] == gen.json()["path_id"]
    assert _order(got.json()) == _order(gen.json())


async def test_roadmap_items_carry_their_resource(api: AsyncClient) -> None:
    """Every catalogue-backed item must say where it lives.

    The roadmap used to name a course without carrying its URL, so a client
    could only link the handful of items that also appeared in the separate
    recommendations response — the rest were dead titles the learner had no
    way to open.
    """
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    await api.post("/learning-path/generate", headers=h, json=_request(uid))
    roadmap = (await api.get(f"/learning-path/{uid}", headers=h)).json()

    items = [
        item
        for phase in roadmap["phases"]
        for milestone in phase["milestones"]
        for item in milestone["resources"]
    ]
    backed = [i for i in items if i["resource_id"]]
    assert backed, "the plan should draw on the catalogue"
    for item in backed:
        assert item["url"], f"{item['title']} has no link to follow"
        assert item["provider"], f"{item['title']} does not say who made it"
        assert item["skills"], f"{item['title']} does not say what it teaches"

    # Self-study reviews are not catalogue rows and carry nothing to follow.
    for item in items:
        if not item["resource_id"]:
            assert item["url"] is None


async def test_regenerate_supersedes(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    first = await api.post("/learning-path/generate", headers=h, json=_request(uid))
    path_id = first.json()["path_id"]
    regen = await api.post(f"/learning-path/{path_id}/regenerate", headers=h, json={"weekly_hours": 20})
    assert regen.status_code == 200, regen.text
    # a fresh active path exists and is a new version
    active = await api.get(f"/learning-path/{uid}", headers=h)
    assert active.json()["path_id"] == regen.json()["path_id"]
    assert active.json()["path_id"] != path_id
    assert active.json()["version"] >= first.json()["version"]


async def test_cannot_generate_for_another_user(api: AsyncClient) -> None:
    owner, _ = await _learner_with_skills()
    _, other_email = await _learner_with_skills()
    other_h = await _auth(api, other_email)
    r = await api.post("/learning-path/generate", headers=other_h, json=_request(owner))
    assert r.status_code == 403


async def test_get_without_path_404(api: AsyncClient) -> None:
    uid, email = await _learner_with_skills()
    h = await _auth(api, email)
    assert (await api.get(f"/learning-path/{uid}", headers=h)).status_code == 404


async def test_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/learning-path/generate", json={"user_id": str(uuid.uuid4()), "goal_text": "x",
                                                        "target_skills": [{"skill_slug": "python", "required_level": 0.8}]})
    assert r.status_code == 401

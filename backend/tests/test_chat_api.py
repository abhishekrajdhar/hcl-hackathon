"""Integration tests for POST /api/chat — grounded, tool-driven, no hallucination."""

from __future__ import annotations

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
from app.models.skill import UserSkill
from app.repositories.skill import SkillRepository
from app.repositories.user import LearnerProfileRepository, UserRepository

pytestmark = pytest.mark.asyncio
PW = "chat-pw-12345"


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


async def _auth(api: AsyncClient, email: str) -> dict[str, str]:
    r = await api.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _new_learner(api: AsyncClient, *, with_path: bool = True) -> tuple[uuid.UUID, dict]:
    email = f"chat-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as s:
        user = await UserRepository(s).create({"email": email, "hashed_password": hash_password(PW)})
        await s.flush()
        await LearnerProfileRepository(s).create({"user_id": user.id, "weekly_hours": 10})
        skills = SkillRepository(s)
        for slug, prof in [("python", 0.85), ("statistics", 0.5)]:
            sk = await skills.get_by_slug(slug)
            s.add(UserSkill(user_id=user.id, skill_id=sk.id, proficiency=prof,
                            current_level=prof * sk.level_scale, confidence=0.7))
        await s.commit()
        uid = user.id
    h = await _auth(api, email)
    if with_path:
        await api.post("/learning-path/generate", headers=h, json={
            "user_id": str(uid),
            "target_skills": [{"skill_slug": "machine-learning", "required_level": 0.8},
                              {"skill_slug": "deep-learning", "required_level": 0.7}],
            "goal_text": "ML engineer",
        })
    return uid, h


async def test_next_action_uses_the_path_tool(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    r = await api.post("/chat", headers=h, json={"message": "What should I learn next?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "next_action"
    assert "get_next_action" in [t["name"] for t in body["tools_used"]]
    # the reply names a real path item (grounded), not an invented one
    tool = next(t for t in body["tools_used"] if t["name"] == "get_next_action")
    assert tool["available"] is True
    assert tool["data"]["title"].lower() in body["reply"].lower()


async def test_can_i_skip_is_grounded_in_gaps(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    r = await api.post("/chat", headers=h, json={"message": "Can I skip statistics?"})
    body = r.json()
    assert body["intent"] == "can_i_skip"
    # references the learner's real levels
    assert "50%" in body["reply"] and "80%" in body["reply"]


async def test_no_hallucination_when_data_absent(api: AsyncClient) -> None:
    # a learner with NO path -> the assistant must say so, not invent one
    uid, h = await _new_learner(api, with_path=False)
    r = await api.post("/chat", headers=h, json={"message": "What should I learn next?"})
    body = r.json()
    tool = next(t for t in body["tools_used"] if t["name"] == "get_next_action")
    assert tool["available"] is False
    reply = body["reply"].lower()
    assert "don't have" in reply or "no active" in reply or "set a goal" in reply


async def test_explain_unknown_recommendation_does_not_invent(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    # no recommendations persisted -> must not fabricate a reason
    r = await api.post("/chat", headers=h, json={"message": "Why are you recommending PyTorch?"})
    body = r.json()
    assert body["intent"] == "explain_recommendation"
    reply = body["reply"].lower()
    assert ("don't have any active recommendations" in reply
            or "not currently recommending" in reply)


async def test_report_score_records_via_tool(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    r = await api.post("/chat", headers=h, json={"message": "I scored 92% on the assessment."})
    body = r.json()
    assert body["intent"] == "report_score"
    tool = next(t for t in body["tools_used"] if t["name"] == "update_learning_progress")
    assert tool["available"] is True
    assert tool["data"]["updated_skills"]  # a real skill was updated


async def test_search_resources_returns_catalogue_hits(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    r = await api.post("/chat", headers=h, json={"message": "find courses on transformers"})
    body = r.json()
    assert body["intent"] == "search_resources"
    tool = next(t for t in body["tools_used"] if t["name"] == "search_resources")
    assert tool["data"]["results"]
    assert "transformer" in body["reply"].lower()


async def test_conversation_history_is_stored_and_separate(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    r1 = await api.post("/chat", headers=h, json={"message": "show me my roadmap"})
    convo_id = r1.json()["conversation_id"]
    r2 = await api.post("/chat", headers=h,
                        json={"message": "how am I doing?", "conversation_id": convo_id})
    assert r2.json()["conversation_id"] == convo_id

    history = await api.get(f"/chat/conversations/{convo_id}", headers=h)
    assert history.status_code == 200
    roles = [m["role"] for m in history.json()["messages"]]
    # two user turns + two assistant turns, in order
    assert roles == ["user", "assistant", "user", "assistant"]
    # meta records which tools ran (dialogue memory, not app state)
    assistant_msgs = [m for m in history.json()["messages"] if m["role"] == "assistant"]
    assert all("tools_used" in m["meta"] for m in assistant_msgs)


async def test_llm_rephrase_is_grounded_or_falls_back(api: AsyncClient) -> None:
    uid, h = await _new_learner(api)
    # a hallucinated LLM rephrase (invents "99% in Rust") must be rejected
    app.dependency_overrides[get_llm_provider_dep] = lambda: MockProvider(
        responses=["You are 99% proficient in Rust and ready for a senior role."]
    )
    r = await api.post("/chat", headers=h, json={"message": "What should I learn next?"})
    body = r.json()
    assert body["source"] == "template"  # ungrounded LLM output rejected
    assert "Rust" not in body["reply"]


async def test_set_goal_updates_profile(api: AsyncClient) -> None:
    uid, h = await _new_learner(api, with_path=False)
    r = await api.post("/chat", headers=h,
                       json={"message": "I want to become a computer vision engineer."})
    assert r.json()["intent"] == "set_goal"
    # the goal was actually saved to the profile (state, not memory)
    profile = await api.get(f"/profile/{uid}", headers=h)
    assert profile.json()["profile"]["target_role"] == "computer vision engineer"


async def test_cannot_continue_another_users_conversation(api: AsyncClient) -> None:
    _, owner_h = await _new_learner(api, with_path=False)
    r1 = await api.post("/chat", headers=owner_h, json={"message": "hello"})
    convo_id = r1.json()["conversation_id"]
    _, other_h = await _new_learner(api, with_path=False)
    r2 = await api.post("/chat", headers=other_h,
                        json={"message": "hi", "conversation_id": convo_id})
    assert r2.status_code == 403


async def test_requires_auth(api: AsyncClient) -> None:
    r = await api.post("/chat", json={"message": "hello"})
    assert r.status_code == 401

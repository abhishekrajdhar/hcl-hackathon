"""Integration tests for the agentic discovery seam.

The model is a seeded MockProvider, so what is under test is the seam itself:
schema validation, grounding against the real skill graph, and the
deterministic fallback when the model's output is unusable.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.engines.discovery import ROLES
from app.llm.providers.mock import MockProvider
from app.repositories.user import UserRepository
from app.models.enums import UserRole
from app.services.discovery_service import CareerDiscoveryService

pytestmark = pytest.mark.asyncio


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            n = (await session.execute(text("select count(*) from skills"))).scalar_one()
            return int(n) > 0
    except Exception:  # noqa: BLE001
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_db() -> None:
    if not await _seeded():
        pytest.skip("database not reachable or not seeded", allow_module_level=True)


@pytest_asyncio.fixture(autouse=True)
def _agentic_on(monkeypatch: pytest.MonkeyPatch):
    # The service refuses to spend the mock's repair loop in production; tests
    # simulate a real provider, so lift the gate.
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")


@pytest_asyncio.fixture
async def user_id() -> uuid.UUID:
    async with SessionLocal() as session:
        user = await UserRepository(session).create(
            {
                "email": f"discovery-{uuid.uuid4().hex[:10]}@example.com",
                "hashed_password": hash_password("discovery-pw-123"),
                "role": UserRole.LEARNER,
            }
        )
        await session.commit()
        return user.id


def _advice(careers: list[dict]) -> str:
    return json.dumps({"careers": careers})


async def test_model_proposal_is_grounded_and_invented_skills_dropped(user_id) -> None:
    provider = MockProvider(responses=[_advice([
        {
            "title": "Speech Interface Engineer",
            "pitch": "Build systems that understand and generate speech.",
            "why": "You said you enjoy language.",
            # one real catalogue skill, one invention
            "target_skills": ["NLP Fundamentals", "Quantum Telepathy Studies"],
        },
    ])])
    async with SessionLocal() as session:
        out = await CareerDiscoveryService(session, provider).discover(
            user_id, interests=["language"], free_text="", top_k=3
        )
    assert out[0].title == "Speech Interface Engineer"
    slugs = [t.skill_slug for t in out[0].target_skills]
    assert slugs == ["nlp-fundamentals"], "the invented skill must be dropped, the real one kept"
    assert out[0].reasons == ["You said you enjoy language."]


async def test_direction_built_entirely_on_invented_skills_is_discarded(user_id) -> None:
    provider = MockProvider(responses=[
        _advice([
            {"title": "Dream Architect", "pitch": "Design dreams for a living today.",
             "why": "Because dreams.", "target_skills": ["Oneirology", "Lucid Engineering"]},
            {"title": "ML Practitioner", "pitch": "Apply machine learning to real problems.",
             "why": "You already know Python.", "target_skills": ["Machine Learning Foundations"]},
        ])
    ])
    async with SessionLocal() as session:
        out = await CareerDiscoveryService(session, provider).discover(
            user_id, interests=[], free_text="", top_k=3
        )
    titles = [c.title for c in out]
    assert "Dream Architect" not in titles
    assert "ML Practitioner" in titles


async def test_unusable_model_output_falls_back_to_the_static_engine(user_id) -> None:
    # Both the first attempt and the repair attempt return garbage.
    provider = MockProvider(responses=["not json at all", "still not json"])
    async with SessionLocal() as session:
        out = await CareerDiscoveryService(session, provider).discover(
            user_id, interests=["language"], free_text="", top_k=3
        )
    assert out, "fallback must answer when the model cannot"
    static_slugs = {r.slug for r in ROLES}
    assert all(c.slug in static_slugs for c in out), "fallback answers come from the curated engine"


async def test_no_provider_uses_the_static_engine(user_id) -> None:
    async with SessionLocal() as session:
        out = await CareerDiscoveryService(session, None).discover(
            user_id, interests=["images"], free_text="", top_k=3
        )
    assert out[0].slug == "computer-vision-engineer"


async def test_goal_reading_parses_and_survives_garbage(user_id) -> None:
    good = MockProvider(responses=[json.dumps(
        {"is_goal": True, "uncertain": False,
         "goal_text": "computer vision engineer", "goal_type": "career"}
    )])
    bad = MockProvider(responses=["nonsense"])
    async with SessionLocal() as session:
        service_good = CareerDiscoveryService(session, good)
        service_bad = CareerDiscoveryService(session, bad)
        reading = await service_good.read_goal("i wanna do the vision stuff with cameras")
        assert reading is not None and reading.goal_type == "career"
        assert await service_bad.read_goal("anything") is None, "garbage -> regex verdict stands"

"""Integration tests for dynamic role graphs.

The model is a seeded MockProvider; under test is the materialisation seam —
skills grown idempotently, cycles refused, targets usable by the gap engine —
and the fallback ladder beneath it.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import ValidationError
from app.db.session import SessionLocal
from app.llm.providers.mock import MockProvider
from app.services.role_graph_service import RoleGraphService

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
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")


def _spec(skills: list[dict], title: str = "Backend Developer") -> str:
    return json.dumps({"role_title": title, "skills": skills})


UNIQ = uuid.uuid4().hex[:6]


async def test_design_is_materialised_and_reused_skills_are_not_duplicated() -> None:
    new_a = f"Operating Systems {UNIQ}"
    new_b = f"Computer Networks {UNIQ}"
    spec = _spec([
        {"name": "Python", "required_level": 0.8, "prerequisites": [], "category": "Programming"},
        {"name": new_b, "required_level": 0.7, "prerequisites": ["Python"],
         "category": "Programming", "difficulty": 3},
        {"name": new_a, "required_level": 0.7, "prerequisites": [new_b],
         "category": "Programming", "difficulty": 4},
    ])
    async with SessionLocal() as session:
        service = RoleGraphService(session, MockProvider(responses=[spec]))
        targets = await service.targets_for_goal(f"backend developer {UNIQ}")
        await session.commit()
    assert len(targets) == 3

    async with SessionLocal() as session:
        # Python resolved to the EXISTING catalogue row, not a duplicate.
        n = (await session.execute(
            text("select count(*) from skills where slug = 'python'")
        )).scalar_one()
        assert int(n) == 1
        # The new skills exist exactly once, marked with their origin.
        for slug_base in ("operating-systems", "computer-networks"):
            rows = (await session.execute(
                text("select extra from skills where slug = :s"),
                {"s": f"{slug_base}-{UNIQ}"},
            )).all()
            assert len(rows) == 1, slug_base
            assert rows[0][0].get("origin") == "role_graph"
        # The prerequisite edge landed and is queryable by the gap engine.
        edge = (await session.execute(text(
            """select count(*) from prerequisites p
               join skills s on s.id = p.source_skill_id
               join skills q on q.id = p.prerequisite_skill_id
               where s.slug = :src and q.slug = :pre"""),
            {"src": f"operating-systems-{UNIQ}", "pre": f"computer-networks-{UNIQ}"},
        )).scalar_one()
        assert int(edge) == 1


async def test_second_run_of_the_same_role_converges_not_duplicates() -> None:
    spec = _spec([
        {"name": "Python", "required_level": 0.8, "prerequisites": [], "category": "Programming"},
        {"name": f"Computer Networks {UNIQ}", "required_level": 0.7,
         "prerequisites": [], "category": "Programming"},
        {"name": f"Operating Systems {UNIQ}", "required_level": 0.7,
         "prerequisites": [f"Computer Networks {UNIQ}"], "category": "Programming"},
    ])
    async with SessionLocal() as session:
        service = RoleGraphService(session, MockProvider(responses=[spec]))
        targets = await service.targets_for_goal(f"another backend goal {UNIQ}")
        await session.commit()
    assert len(targets) == 3
    async with SessionLocal() as session:
        n = (await session.execute(
            text("select count(*) from skills where slug = :s"),
            {"s": f"operating-systems-{UNIQ}"},
        )).scalar_one()
        assert int(n) == 1, "re-running the role must resolve, not duplicate"


async def test_a_cycle_in_the_design_is_refused_not_written() -> None:
    a, b = f"Cycle Alpha {UNIQ}", f"Cycle Beta {UNIQ}"
    spec = _spec([
        {"name": "Python", "required_level": 0.8, "prerequisites": [], "category": "Programming"},
        {"name": a, "required_level": 0.6, "prerequisites": [b], "category": "Programming"},
        {"name": b, "required_level": 0.6, "prerequisites": [a], "category": "Programming"},
    ])
    async with SessionLocal() as session:
        service = RoleGraphService(session, MockProvider(responses=[spec]))
        targets = await service.targets_for_goal(f"cyclic role {UNIQ}")
        await session.commit()
    assert len(targets) == 3, "all skills exist; only the cycling edge is dropped"
    async with SessionLocal() as session:
        n = (await session.execute(text(
            """select count(*) from prerequisites p
               join skills s on s.id = p.source_skill_id
               join skills q on q.id = p.prerequisite_skill_id
               where s.slug like :a and q.slug like :b"""),
            {"a": f"cycle-%-{UNIQ}", "b": f"cycle-%-{UNIQ}"},
        )).scalar_one()
        assert int(n) <= 1, "at most one direction of the cycle may exist"


async def test_mock_provider_falls_back_to_nearest_curated_role() -> None:
    # This is the exact dead end a learner hit: "backend developer" under the
    # mock provider. The static career engine's data-engineer role carries the
    # keyword "backend", so the ladder lands there instead of on a wall.
    async with SessionLocal() as session:
        service = RoleGraphService(session, None)
        targets = await service.targets_for_goal("backend developer")
    assert targets, "the curated fallback must answer"


async def test_unmappable_goal_is_a_422_pointing_at_discovery() -> None:
    async with SessionLocal() as session:
        service = RoleGraphService(session, None)
        with pytest.raises(ValidationError) as err:
            await service.targets_for_goal("championship snail racing")
    assert "career discovery" in str(err.value).lower()

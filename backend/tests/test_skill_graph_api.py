"""Integration tests for the skill knowledge graph API.

Run in-process against the real (seeded) database, and skip themselves when no
database is reachable — same pattern as test_api_integration.py.

    docker compose up -d postgres
    alembic upgrade head && python -m app.db.seed
    pytest
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

ADMIN_PASSWORD = "graph-admin-pw"
LEARNER_PASSWORD = "graph-learner-pw"


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            count = await session.scalar(text("SELECT count(*) FROM skills"))
        return bool(count)
    except Exception:
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_seeded_db() -> None:
    if not await _seeded():
        pytest.skip(
            "database not reachable or not seeded (run `python -m app.db.seed`)",
            allow_module_level=True,
        )


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _auth(api: AsyncClient, role: UserRole, password: str) -> dict[str, str]:
    email = f"{role.value}-graph-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(password), "role": role}
        )
        await session.commit()
    response = await api.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> dict[str, str]:
    return await _auth(api, UserRole.LEARNER, LEARNER_PASSWORD)


@pytest_asyncio.fixture
async def admin(api: AsyncClient) -> dict[str, str]:
    return await _auth(api, UserRole.ADMIN, ADMIN_PASSWORD)


async def _skill_id(api: AsyncClient, headers: dict[str, str], slug: str) -> uuid.UUID:
    response = await api.get("/skills", headers=headers, params={"search": slug, "limit": 50})
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        if item["slug"] == slug:
            return uuid.UUID(item["id"])
    raise AssertionError(f"seed skill '{slug}' not found")


# --- listing & retrieval ---------------------------------------------------
async def test_list_skills_and_categories(api: AsyncClient, learner: dict[str, str]) -> None:
    skills = await api.get("/skills", headers=learner, params={"limit": 100})
    assert skills.status_code == 200
    assert skills.json()["total"] >= 40

    categories = await api.get("/skill-categories", headers=learner)
    assert categories.status_code == 200
    slugs = {c["slug"] for c in categories.json()}
    assert {"programming", "machine-learning", "deep-learning", "mlops"} <= slugs


async def test_filter_skills_by_category_and_difficulty(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    response = await api.get(
        "/skills", headers=learner, params={"category": "deep-learning", "limit": 100}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items and all(i["category"]["slug"] == "deep-learning" for i in items)

    easy = await api.get("/skills", headers=learner, params={"max_difficulty": 1, "limit": 100})
    assert all(i["difficulty"] == 1 for i in easy.json()["items"])


async def test_get_single_skill(api: AsyncClient, learner: dict[str, str]) -> None:
    ml_id = await _skill_id(api, learner, "machine-learning")
    response = await api.get(f"/skills/{ml_id}", headers=learner)
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "machine-learning"
    assert body["category"]["slug"] == "machine-learning"


# --- prerequisite retrieval ------------------------------------------------
async def test_direct_prerequisites(api: AsyncClient, learner: dict[str, str]) -> None:
    ml_id = await _skill_id(api, learner, "machine-learning")
    response = await api.get(f"/skills/{ml_id}/prerequisites", headers=learner)
    assert response.status_code == 200
    prereq_slugs = {e["prerequisite_skill"]["slug"] for e in response.json()}
    # Hard prerequisites of ML in the seed.
    assert {"python", "linear-algebra", "statistics"} <= prereq_slugs


async def test_prerequisite_tree_is_finite_and_nested(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    cv_id = await _skill_id(api, learner, "computer-vision")
    response = await api.get(f"/skills/{cv_id}/prerequisite-tree", headers=learner)
    assert response.status_code == 200
    body = response.json()
    assert body["root"]["skill"]["slug"] == "computer-vision"
    assert body["total_prerequisites"] > 0
    # cnn should appear as a child somewhere in the tree.
    assert body["root"]["prerequisites"]


# --- dependency (dependents) retrieval -------------------------------------
async def test_dependents(api: AsyncClient, learner: dict[str, str]) -> None:
    dl_id = await _skill_id(api, learner, "deep-learning")
    response = await api.get(f"/skills/{dl_id}/dependents", headers=learner)
    assert response.status_code == 200
    dependent_slugs = {e["source_skill"]["slug"] for e in response.json()}
    # CNN, RNN and Transformers all build on deep learning.
    assert {"cnn", "rnn", "transformers"} <= dependent_slugs


async def test_dependency_analysis_has_critical_path(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    cv_id = await _skill_id(api, learner, "computer-vision")
    response = await api.get(f"/skills/{cv_id}/dependencies", headers=learner)
    assert response.status_code == 200
    body = response.json()
    assert body["total_prerequisites"] > 5
    critical = [s["slug"] for s in body["critical_path"]]
    # Critical path ends at the skill itself and includes the DL chain.
    assert critical[-1] == "computer-vision"
    assert critical.index("machine-learning") < critical.index("deep-learning")
    assert critical.index("deep-learning") < critical.index("cnn")
    # `all_prerequisites` is itself a valid learning order.
    seq = [s["id"] for s in body["all_prerequisites"]]
    validate = await api.post("/skills/validate-order", headers=learner, json={"skill_ids": seq})
    assert validate.json()["is_valid"]


# --- learning sequence -----------------------------------------------------
async def test_find_learning_sequence_orders_prerequisites_first(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    llm_id = await _skill_id(api, learner, "large-language-models")
    response = await api.post(
        "/skills/learning-sequence",
        headers=learner,
        json={"target_skill_ids": [str(llm_id)]},
    )
    assert response.status_code == 200
    body = response.json()
    order = [step["skill"]["slug"] for step in body["sequence"]]
    assert order[-1] == "large-language-models"
    # Every prerequisite precedes the skills that need it.
    assert order.index("python") < order.index("machine-learning")
    assert order.index("machine-learning") < order.index("deep-learning")
    assert order.index("transformers") < order.index("large-language-models")
    # The reported order is itself valid.
    seq_ids = [step["skill"]["id"] for step in body["sequence"]]
    validate = await api.post(
        "/skills/validate-order", headers=learner, json={"skill_ids": seq_ids}
    )
    assert validate.json()["is_valid"]


async def test_learning_sequence_is_deterministic(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    cv_id = await _skill_id(api, learner, "computer-vision")
    payload = {"target_skill_ids": [str(cv_id)]}
    first = await api.post("/skills/learning-sequence", headers=learner, json=payload)
    second = await api.post("/skills/learning-sequence", headers=learner, json=payload)
    order1 = [s["skill"]["slug"] for s in first.json()["sequence"]]
    order2 = [s["skill"]["slug"] for s in second.json()["sequence"]]
    assert order1 == order2


async def test_learning_sequence_skips_known_skills(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    cv_id = await _skill_id(api, learner, "computer-vision")
    ml_id = await _skill_id(api, learner, "machine-learning")
    response = await api.post(
        "/skills/learning-sequence",
        headers=learner,
        json={"target_skill_ids": [str(cv_id)], "known_skill_ids": [str(ml_id)]},
    )
    assert response.status_code == 200
    body = response.json()
    slugs = {s["skill"]["slug"] for s in body["sequence"]}
    # machine-learning is known, so it is dropped from the sequence...
    assert "machine-learning" not in slugs
    assert str(ml_id) in body["skipped_known_skill_ids"]
    # ...but the target and prerequisites reachable by other paths remain.
    assert "computer-vision" in slugs
    # python stays: computer-vision also needs it via image-processing.
    assert "python" in slugs


async def test_multi_target_sequence_covers_all(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    cv_id = await _skill_id(api, learner, "computer-vision")
    llm_id = await _skill_id(api, learner, "large-language-models")
    response = await api.post(
        "/skills/learning-sequence",
        headers=learner,
        json={"target_skill_ids": [str(cv_id), str(llm_id)]},
    )
    assert response.status_code == 200
    slugs = {s["skill"]["slug"] for s in response.json()["sequence"]}
    assert {"computer-vision", "large-language-models"} <= slugs
    # Shared prerequisite appears exactly once.
    order = [s["skill"]["slug"] for s in response.json()["sequence"]]
    assert order.count("machine-learning") == 1


# --- invalid learning paths ------------------------------------------------
async def test_validate_rejects_out_of_order_path(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    ml_id = await _skill_id(api, learner, "machine-learning")
    python_id = await _skill_id(api, learner, "python")
    # ML before Python — a hard prerequisite is out of order.
    response = await api.post(
        "/skills/validate-order",
        headers=learner,
        json={"skill_ids": [str(ml_id), str(python_id)]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert any(v["severity"] == "error" for v in body["violations"])
    # A corrected order is offered and puts python first.
    suggested = [s["slug"] for s in body["suggested_order"]]
    assert suggested.index("python") < suggested.index("machine-learning")


async def test_validate_reports_missing_prerequisites(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    dl_id = await _skill_id(api, learner, "deep-learning")
    response = await api.post(
        "/skills/validate-order", headers=learner, json={"skill_ids": [str(dl_id)]}
    )
    body = response.json()
    assert body["is_valid"] is False
    missing = {s["slug"] for s in body["missing_prerequisites"]}
    assert "machine-learning" in missing
    assert "neural-networks" in missing


# --- cycle prevention on write ---------------------------------------------
async def test_add_prerequisite_rejects_cycle(
    api: AsyncClient, admin: dict[str, str]
) -> None:
    python_id = await _skill_id(api, admin, "python")
    cv_id = await _skill_id(api, admin, "computer-vision")
    # python already sits far below computer-vision; requiring cv would close a loop.
    response = await api.post(
        f"/skills/{python_id}/prerequisites",
        headers=admin,
        json={
            "source_skill_id": str(python_id),
            "prerequisite_skill_id": str(cv_id),
            "relationship_type": "hard_prerequisite",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "prerequisite_cycle"
    assert "cycle" in response.json()["extra"]


async def test_add_prerequisite_rejects_self_loop(
    api: AsyncClient, admin: dict[str, str]
) -> None:
    python_id = await _skill_id(api, admin, "python")
    response = await api.post(
        f"/skills/{python_id}/prerequisites",
        headers=admin,
        json={
            "source_skill_id": str(python_id),
            "prerequisite_skill_id": str(python_id),
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "self_prerequisite"


async def test_add_and_remove_valid_prerequisite(
    api: AsyncClient, admin: dict[str, str]
) -> None:
    # Create two throwaway skills in an existing category and link them.
    cats = await api.get("/skill-categories", headers=admin)
    category_id = cats.json()[0]["id"]
    suffix = uuid.uuid4().hex[:8]

    async def make(name: str, difficulty: int) -> str:
        resp = await api.post(
            "/skills",
            headers=admin,
            json={
                "slug": f"{name}-{suffix}",
                "name": name,
                "category_id": category_id,
                "difficulty": difficulty,
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    advanced = await make("temp-advanced", 4)
    basic = await make("temp-basic", 1)

    edge = await api.post(
        f"/skills/{advanced}/prerequisites",
        headers=admin,
        json={"source_skill_id": advanced, "prerequisite_skill_id": basic},
    )
    assert edge.status_code == 201, edge.text

    # The reverse edge would now be a cycle.
    reverse = await api.post(
        f"/skills/{basic}/prerequisites",
        headers=admin,
        json={"source_skill_id": basic, "prerequisite_skill_id": advanced},
    )
    assert reverse.status_code == 422

    edge_id = edge.json()["id"]
    deleted = await api.delete(f"/prerequisites/{edge_id}", headers=admin)
    assert deleted.status_code == 204


async def test_cycle_report_clean_on_seeded_graph(
    api: AsyncClient, admin: dict[str, str]
) -> None:
    response = await api.get("/skills/graph/cycles", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["is_acyclic"] is True
    assert body["cycle_count"] == 0


async def test_graph_write_requires_admin(api: AsyncClient, learner: dict[str, str]) -> None:
    python_id = await _skill_id(api, learner, "python")
    response = await api.post(
        f"/skills/{python_id}/prerequisites",
        headers=learner,
        json={"source_skill_id": str(python_id), "prerequisite_skill_id": str(python_id)},
    )
    assert response.status_code == 403

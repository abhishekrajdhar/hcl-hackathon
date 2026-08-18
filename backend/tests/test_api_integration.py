"""End-to-end API tests.

These run in-process against the real database, so they are skipped when no
database is reachable (e.g. a bare `pytest` run with nothing else started).

    docker compose up -d postgres && alembic upgrade head && pytest
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

ADMIN_PASSWORD = "integration-admin-pw"
LEARNER_PASSWORD = "integration-learner-pw"


async def _database_available() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1 FROM users LIMIT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_database() -> None:
    if not await _database_available():
        pytest.skip("database not reachable or not migrated", allow_module_level=True)


@pytest_asyncio.fixture
async def api() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


async def _make_user(role: UserRole, password: str) -> str:
    email = f"{role.value}-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as session:
        await UserRepository(session).create(
            {"email": email, "hashed_password": hash_password(password), "role": role}
        )
        await session.commit()
    return email


async def _auth_header(api: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await api.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin(api: AsyncClient) -> dict[str, str]:
    email = await _make_user(UserRole.ADMIN, ADMIN_PASSWORD)
    return await _auth_header(api, email, ADMIN_PASSWORD)


@pytest_asyncio.fixture
async def learner(api: AsyncClient) -> dict[str, str]:
    email = await _make_user(UserRole.LEARNER, LEARNER_PASSWORD)
    return await _auth_header(api, email, LEARNER_PASSWORD)


async def _make_category(api: AsyncClient, admin: dict[str, str]) -> str:
    slug = f"cat-{uuid.uuid4().hex[:8]}"
    response = await api.post(
        "/skill-categories", headers=admin, json={"slug": slug, "name": slug}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _make_skill(api: AsyncClient, admin: dict[str, str], name: str) -> str:
    slug = f"{name}-{uuid.uuid4().hex[:8]}"
    category_id = await _make_category(api, admin)
    response = await api.post(
        "/skills",
        headers=admin,
        json={"slug": slug, "name": name, "category_id": category_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- auth & authorization --------------------------------------------------
async def test_register_and_login(api: AsyncClient) -> None:
    email = f"signup-{uuid.uuid4().hex[:10]}@example.com"
    response = await api.post(
        "/auth/register", json={"email": email, "password": "a-good-password"}
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "learner"

    duplicate = await api.post(
        "/auth/register", json={"email": email, "password": "a-good-password"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "email_taken"

    bad = await api.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"


async def test_catalogue_writes_require_admin(api: AsyncClient, learner: dict[str, str]) -> None:
    response = await api.post(
        "/skills", headers=learner, json={"slug": f"x-{uuid.uuid4().hex[:8]}", "name": "X"}
    )
    assert response.status_code == 403


# --- prerequisite graph ----------------------------------------------------
async def test_prerequisite_cycle_is_rejected(
    api: AsyncClient, admin: dict[str, str], learner: dict[str, str]
) -> None:
    algebra = await _make_skill(api, admin, "algebra")
    ml = await _make_skill(api, admin, "ml")
    nn = await _make_skill(api, admin, "nn")

    for skill, prereq in ((ml, algebra), (nn, ml)):
        response = await api.post(
            f"/skills/{skill}/prerequisites",
            headers=admin,
            json={"source_skill_id": skill, "prerequisite_skill_id": prereq},
        )
        assert response.status_code == 201, response.text

    # algebra -> nn would close the loop algebra -> nn -> ml -> algebra.
    cycle = await api.post(
        f"/skills/{algebra}/prerequisites",
        headers=admin,
        json={"source_skill_id": algebra, "prerequisite_skill_id": nn},
    )
    assert cycle.status_code == 422
    assert cycle.json()["code"] == "prerequisite_cycle"

    graph = await api.get(f"/skills/{nn}/graph", headers=learner)
    assert graph.status_code == 200
    depths = {n["skill_id"]: n["depth"] for n in graph.json()["nodes"]}
    assert depths[nn] == 0
    assert depths[ml] == 1
    assert depths[algebra] == 2


# --- assessment grading ----------------------------------------------------
async def test_grading_is_deterministic(
    api: AsyncClient, admin: dict[str, str], learner: dict[str, str]
) -> None:
    skill = await _make_skill(api, admin, "grading")
    created = await api.post(
        "/assessments",
        headers=admin,
        json={
            "skill_id": skill,
            "title": "Checkpoint",
            "passing_score": 0.6,
            "questions": [
                {
                    "order_index": 0,
                    "question_type": "single_choice",
                    "stem": "Pick a",
                    "options": [{"key": "a"}, {"key": "b"}],
                    "correct_answer": {"value": "a"},
                    "points": 1,
                },
                {
                    "order_index": 1,
                    "question_type": "multiple_choice",
                    "stem": "Pick a and b",
                    "options": [{"key": "a"}, {"key": "b"}, {"key": "c"}],
                    "correct_answer": {"value": ["a", "b"]},
                    "points": 2,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    assessment_id = created.json()["id"]

    # The learner-facing view must never expose the answer key.
    assert all("correct_answer" not in q for q in created.json()["questions"])

    keyed = await api.get(f"/assessments/{assessment_id}/questions", headers=admin)
    q0, q1 = sorted(keyed.json(), key=lambda q: q["order_index"])

    passing = await api.post(
        f"/assessments/{assessment_id}/submit",
        headers=learner,
        json={
            "answers": [
                {"question_id": q0["id"], "response": "a"},
                # order must not matter for multiple choice
                {"question_id": q1["id"], "response": ["b", "a"]},
            ]
        },
    )
    assert passing.status_code == 201, passing.text
    assert passing.json()["score"] == 3.0
    assert passing.json()["passed"] is True

    failing = await api.post(
        f"/assessments/{assessment_id}/submit",
        headers=learner,
        json={
            "answers": [
                {"question_id": q0["id"], "response": "b"},
                {"question_id": q1["id"], "response": ["c"]},
            ]
        },
    )
    assert failing.json()["score"] == 0.0
    assert failing.json()["passed"] is False


# --- path, progress, ownership --------------------------------------------
async def test_path_progress_and_ownership(
    api: AsyncClient, admin: dict[str, str], learner: dict[str, str]
) -> None:
    skill = await _make_skill(api, admin, "pathing")
    resource = await api.post(
        "/resources",
        headers=admin,
        json={
            "provider": "test",
            "title": "A course",
            "url": "https://example.test/course",
            "estimated_hours": 1.0,
            "skills": [{"skill_id": skill, "teaches_level_from": 0, "teaches_level_to": 3}],
        },
    )
    assert resource.status_code == 201, resource.text
    resource_id = resource.json()["id"]

    created = await api.post(
        "/learning-paths",
        headers=learner,
        json={
            "title": "My path",
            "items": [
                {
                    "order_index": 0,
                    "title": "Step one",
                    "resource_id": resource_id,
                    "estimated_minutes": 60,
                },
                {
                    "order_index": 1,
                    "title": "Step two",
                    "resource_id": resource_id,
                    "estimated_minutes": 30,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    path = created.json()
    assert path["total_estimated_minutes"] == 90
    path_id = path["id"]
    first_item = min(path["items"], key=lambda i: i["order_index"])

    clash = await api.post(
        f"/learning-paths/{path_id}/items",
        headers=learner,
        json={"order_index": 0, "title": "Clash", "resource_id": resource_id},
    )
    assert clash.status_code == 409

    activated = await api.patch(
        f"/learning-paths/{path_id}", headers=learner, json={"status": "active"}
    )
    assert activated.status_code == 200
    assert activated.json()["started_at"] is not None

    for event in ("started", "completed"):
        response = await api.post(
            "/progress/events",
            headers=learner,
            json={
                "path_item_id": first_item["id"],
                "event_type": event,
                "time_spent_minutes": 45 if event == "completed" else 0,
            },
        )
        assert response.status_code == 201, response.text

    items = await api.get(f"/learning-paths/{path_id}/items", headers=learner)
    statuses = {i["id"]: i["status"] for i in items.json()}
    assert statuses[first_item["id"]] == "completed"

    summary = await api.get("/progress/summary", headers=learner)
    body = summary.json()
    assert body["active_path_id"] == path_id
    assert body["active_path_total_items"] == 2
    assert body["active_path_completed_items"] == 1
    assert body["completion_pct"] == 50.0
    assert body["total_time_minutes"] == 45

    # A different learner must not be able to see or touch any of it.
    other_email = await _make_user(UserRole.LEARNER, LEARNER_PASSWORD)
    other = await _auth_header(api, other_email, LEARNER_PASSWORD)
    assert (await api.get(f"/learning-paths/{path_id}", headers=other)).status_code == 404
    denied = await api.post(
        "/progress/events",
        headers=other,
        json={"path_item_id": first_item["id"], "event_type": "started"},
    )
    assert denied.status_code == 404


async def test_missing_resource_returns_problem_json(
    api: AsyncClient, learner: dict[str, str]
) -> None:
    response = await api.get(f"/skills/{uuid.uuid4()}", headers=learner)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_found"

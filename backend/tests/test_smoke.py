"""Checks that need no database."""

from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app


def test_openapi_schema_builds() -> None:
    schema = app.openapi()
    assert schema["info"]["title"]
    assert "/health" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]


@pytest.mark.asyncio
async def test_liveness(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/health"


@pytest.mark.asyncio
async def test_protected_route_requires_token(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthorized"
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_validation_error_is_problem_json(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_password_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_token_round_trip() -> None:
    import uuid

    user_id = uuid.uuid4()
    token = create_access_token(user_id, role="learner")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "learner"

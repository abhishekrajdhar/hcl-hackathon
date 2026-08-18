"""Liveness and readiness probes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import SessionDep
from app.core.logging import get_logger
from app.schemas.health import ComponentHealth, HealthResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])

_STARTED_AT = time.monotonic()


async def _check_database(session: SessionDep) -> ComponentHealth:
    started = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - probe must never raise
        logger.warning("database health check failed", extra={"error": str(exc)})
        return ComponentHealth(status="error", detail=type(exc).__name__)
    return ComponentHealth(
        status="ok", latency_ms=round((time.perf_counter() - started) * 1000, 2)
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    responses={503: {"description": "One or more components are unhealthy"}},
)
async def health(session: SessionDep, response: Response) -> HealthResponse:
    database = await _check_database(session)
    overall = "ok" if database.status == "ok" else "error"
    if overall != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.monotonic() - _STARTED_AT, 3),
        components={"database": database},
    )


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Process is up. Deliberately does not touch the database."""
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    responses={503: {"description": "Dependencies not ready"}},
)
async def readiness(session: SessionDep, response: Response) -> dict[str, str]:
    database = await _check_database(session)
    if database.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": database.status}
    return {"status": "ok", "database": "ok"}

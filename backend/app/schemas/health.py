from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: Literal["ok", "degraded", "error"]
    detail: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    app: str
    version: str
    environment: str
    uptime_seconds: float
    components: dict[str, ComponentHealth]

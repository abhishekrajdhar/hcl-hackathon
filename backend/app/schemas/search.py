"""Schemas for embedding and semantic-search endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import ResourceType
from app.schemas.resource import ResourceRead


# --- embedding management --------------------------------------------------
class EmbedResourceResponse(BaseModel):
    resource_id: uuid.UUID
    embedded: bool
    dimension: int
    provider: str
    canonical_text: str


class EmbedAllResponse(BaseModel):
    embedded: int
    skipped: int
    total: int
    dimension: int
    provider: str
    only_missing: bool


# --- semantic search -------------------------------------------------------
class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    # Optional structured filters composed with the vector search.
    resource_type: ResourceType | None = None
    max_difficulty: int | None = Field(default=None, ge=1, le=5)
    skill_id: uuid.UUID | None = None


class ResourceSearchResult(BaseModel):
    resource: ResourceRead
    similarity: float = Field(description="Cosine similarity in [-1, 1]; higher is closer")
    distance: float = Field(description="Cosine distance (1 - similarity)")


class SemanticSearchResponse(BaseModel):
    query: str
    provider: str
    count: int
    results: list[ResourceSearchResult] = Field(default_factory=list)


class GoalSearchRequest(BaseModel):
    goal_id: uuid.UUID | None = None
    goal_text: str | None = Field(default=None, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)

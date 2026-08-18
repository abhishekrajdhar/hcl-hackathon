"""Application configuration loaded from environment variables."""

from __future__ import annotations

import functools
import json
from typing import Annotated, Any, Literal

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object. Every value is overridable via the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    APP_NAME: str = "Learning Path Recommender API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["local", "development", "staging", "production"] = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Security --------------------------------------------------------
    SECRET_KEY: str = Field(
        default="CHANGE_ME_INSECURE_DEV_KEY_DO_NOT_USE_IN_PRODUCTION",
        min_length=16,
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # NoDecode: take the raw string so the validator below can accept both a
    # comma-separated list and a JSON array. Without it pydantic-settings tries
    # json.loads() first and fails on "a,b".
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # --- Database --------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "lpr"
    POSTGRES_PASSWORD: str = "lpr"
    POSTGRES_DB: str = "lpr"
    DATABASE_URL: str | None = None

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # --- Cache (reserved for later phases) -------------------------------
    REDIS_URL: str | None = None

    # --- Embeddings ------------------------------------------------------
    # Provider is settings-driven, never hard-coded. "mock" needs no heavy
    # dependency (no torch) and is the default so the backend runs locally and
    # in CI; set "sentence_transformer" (and install sentence-transformers) for
    # real semantic embeddings. EMBEDDING_DIM is pinned because it is the
    # pgvector column width — the mock produces vectors of exactly this size and
    # all-MiniLM-L6-v2 is 384, so they interoperate.
    EMBEDDING_PROVIDER: Literal["mock", "sentence_transformer"] = "mock"
    EMBEDDING_DIM: int = 384
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 64
    #: Bounded in-process cache of query-text -> embedding (repeated searches).
    EMBEDDING_QUERY_CACHE_SIZE: int = 512

    # --- LLM -------------------------------------------------------------
    # Provider is chosen here, never hard-coded in application code. Credentials
    # come from the environment; "mock" needs none and is the safe default so
    # the app runs in dev and CI without any API key.
    LLM_PROVIDER: Literal["mock", "claude", "openai"] = "mock"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_REPAIR_ATTEMPTS: int = 1

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str | None = None

    # --- Logging ---------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # --- Bootstrap admin -------------------------------------------------
    FIRST_ADMIN_EMAIL: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None

    # --- Pagination ------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        """Accept both a JSON array and a comma-separated string."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _upper_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        """Build the async DSN from parts unless one was supplied explicitly."""
        if not self.DATABASE_URL:
            dsn = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
            object.__setattr__(self, "DATABASE_URL", str(dsn))
        return self

    @property
    def sync_database_url(self) -> str:
        """Synchronous DSN, used by tooling that cannot drive asyncio."""
        assert self.DATABASE_URL is not None
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@functools.lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed exactly once per process."""
    return Settings()


settings = get_settings()

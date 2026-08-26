from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """ASGI client. Does not start the lifespan, so no database is required."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
def _pin_mock_providers() -> Generator[None, None, None]:
    """Force the deterministic providers for the whole suite.

    Without this the tests inherit whatever backend/.env sets — so a developer
    who has switched the app to OpenAI would have the suite make real, billed
    API calls, and its results would depend on their configuration. Tests that
    need a model inject a seeded MockProvider explicitly.
    """
    original = (settings.LLM_PROVIDER, settings.EMBEDDING_PROVIDER, settings.OPENAI_API_KEY)
    settings.LLM_PROVIDER = "mock"
    settings.EMBEDDING_PROVIDER = "mock"
    # Also hide the key: a provider constructed directly in a test would
    # otherwise fall back to it and reach the real API.
    settings.OPENAI_API_KEY = None
    # The provider is memoised per process; drop the cached instance.
    from app.embeddings.factory import get_embedding_provider
    from app.llm.factory import get_llm_provider

    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()
    yield
    settings.LLM_PROVIDER, settings.EMBEDDING_PROVIDER, settings.OPENAI_API_KEY = original
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

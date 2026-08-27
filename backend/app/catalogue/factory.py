"""Catalogue-provider selection, from settings and never hard-coded.

Mirrors `app.embeddings.factory` and `app.llm.factory`: a misconfiguration
degrades to the inert provider with a warning rather than taking the process
down, because catalogue ingestion is a background concern and must never be the
reason the API fails to boot.
"""

from __future__ import annotations

import functools

from app.catalogue.base import CatalogueProvider
from app.catalogue.providers.null import NullProvider
from app.catalogue.providers.scrape import ScrapeProvider
from app.catalogue.providers.youtube import YouTubeProvider
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_provider(name: str) -> CatalogueProvider:
    key = name.lower()
    if key == "none":
        return NullProvider()
    if key == "scrape":
        return ScrapeProvider()
    if key == "youtube":
        if not settings.YOUTUBE_API_KEY:
            logger.warning(
                "CATALOGUE_PROVIDER=youtube but YOUTUBE_API_KEY is not set; "
                "falling back to the inert provider so nothing silently scrapes"
            )
            return NullProvider()
        return YouTubeProvider()
    raise ValueError(
        f"Unknown catalogue provider '{name}'. Choose none, youtube or scrape."
    )


@functools.lru_cache
def get_catalogue_provider() -> CatalogueProvider:
    """The configured provider (settings.CATALOGUE_PROVIDER), cached per process."""
    return build_provider(settings.CATALOGUE_PROVIDER)

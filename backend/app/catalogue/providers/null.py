"""The do-nothing provider, and the default.

Ingestion reaches the public internet, so it stays off until someone turns it
on. Every call succeeds and returns nothing, so the pipeline runs end to end in
tests and CI without a key, a network, or a stubbed HTTP layer — and reports
honestly that it found no candidates rather than pretending to have looked.
"""

from __future__ import annotations

from typing import Sequence

from app.catalogue.base import CatalogueProvider, VideoRecord


class NullProvider(CatalogueProvider):
    name = "none"

    async def search(self, query: str, *, limit: int = 10) -> list[str]:
        return []

    async def lookup(self, video_ids: Sequence[str]) -> list[VideoRecord]:
        # Not "unavailable" — unknown. Claiming a video is gone because no
        # provider is configured would deactivate the whole catalogue.
        return []

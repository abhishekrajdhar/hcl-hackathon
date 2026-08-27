"""Scrape-based provider: no API key, no quota, no guarantees.

Exactly the method `scripts/refresh_catalogue.py` uses — search-results page for
candidates, oEmbed for title and channel, watch page for runtime. It exists so
the pipeline is usable before anyone obtains an API key, and so the two paths
can be compared. It is the fallback, not the recommendation: YouTube rate-limits
the watch page aggressively and the results-page shape is undocumented.

Two things it cannot do that the API can:
  * report `defaultAudioLanguage`, so language filtering is unavailable here;
  * distinguish "private" from "rate-limited", so a health check on this
    provider reports unknown rather than deleting anything.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Sequence
from urllib.parse import quote

from app.catalogue.base import CatalogueError, CatalogueProvider, VideoRecord
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_VIDEO_ID = re.compile(r'"videoId":"([\w-]{11})"')
_LENGTH = re.compile(r'"lengthSeconds":"(\d+)"')
_UA = "Mozilla/5.0"


class ScrapeProvider(CatalogueProvider):
    name = "scrape"
    search_cost = 0
    lookup_batch_size = 1  # no batch endpoint exists; one request per video
    #: A throttled oEmbed response is indistinguishable from a deleted video,
    #: so `is_available=False` from here means "no usable answer", never
    #: "confirmed gone". The health check honours this and refuses to
    #: deactivate on it.
    can_prove_absence = False

    #: Concurrency is deliberately low. Bursts are what trip the rate limiter,
    #: and a rate-limited run yields no runtimes at all.
    CONCURRENCY = 3

    async def _fetch(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise CatalogueError("The 'httpx' package is not installed") from exc
        async with httpx.AsyncClient(
            timeout=settings.CATALOGUE_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(url, headers={"User-Agent": _UA, **(headers or {})})
        return response.text

    async def search(self, query: str, *, limit: int = 10) -> list[str]:
        page = await self._fetch(
            f"https://www.youtube.com/results?search_query={quote(query)}"
        )
        ids: list[str] = []
        for match in _VIDEO_ID.finditer(page):
            if match.group(1) not in ids:
                ids.append(match.group(1))
            if len(ids) >= limit:
                break
        return ids

    async def lookup(self, video_ids: Sequence[str]) -> list[VideoRecord]:
        ids = list(dict.fromkeys(video_ids))
        semaphore = asyncio.Semaphore(self.CONCURRENCY)

        async def one(video_id: str) -> VideoRecord:
            async with semaphore:
                return await self._lookup_one(video_id)

        return list(await asyncio.gather(*(one(v) for v in ids)))

    async def _lookup_one(self, video_id: str) -> VideoRecord:
        url = f"https://www.youtube.com/watch?v={video_id}"
        raw = await self._fetch(
            f"https://www.youtube.com/oembed?url={url}&format=json"
        )
        try:
            meta = json.loads(raw)
        except ValueError:
            # oEmbed refusing is the only "does not exist" signal available.
            return VideoRecord(video_id=video_id, title="", channel="",
                               duration_hours=0.0, is_available=False)

        page = await self._fetch(url)
        match = _LENGTH.search(page)
        if match is None:
            # Rate-limited, not deleted. Reporting duration 0.0 makes the
            # selector reject it, which is the safe direction: a candidate we
            # could not measure never enters the catalogue.
            logger.warning("runtime unavailable (likely rate limited)", extra={"video": video_id})
            return VideoRecord(
                video_id=video_id, title=meta.get("title", ""),
                channel=meta.get("author_name", ""), duration_hours=0.0,
            )
        return VideoRecord(
            video_id=video_id,
            title=meta.get("title", ""),
            channel=meta.get("author_name", ""),
            duration_hours=round(int(match.group(1)) / 3600, 3),
        )

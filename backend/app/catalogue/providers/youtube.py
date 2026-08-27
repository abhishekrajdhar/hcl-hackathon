"""YouTube Data API v3.

Quota is the design constraint. `search.list` costs 100 units against a 10,000
unit daily default, so ~95 searches a day; `videos.list` costs 1 unit and takes
50 ids at a time, so re-checking the entire catalogue is 2 units. That asymmetry
is why this provider is an ingestion and health-check backend rather than
something on a request path — see `app.services.catalogue_service`.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.catalogue.base import (
    CatalogueError,
    CatalogueProvider,
    QuotaExceededError,
    VideoRecord,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_API = "https://www.googleapis.com/youtube/v3"
_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def parse_duration_hours(value: str) -> float:
    """ISO 8601 duration -> hours. Unparseable input is 0.0, which the selector
    rejects as too short — a missing runtime must never become a plausible one."""
    match = _ISO_DURATION.match(value or "")
    if not match:
        return 0.0
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    seconds = (
        parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]
    )
    return round(seconds / 3600, 3)


class YouTubeProvider(CatalogueProvider):
    name = "youtube"
    search_cost = 100
    lookup_batch_size = 50
    #: `status.privacyStatus` is a direct statement about the video, and an id
    #: missing from a 200 response genuinely does not exist.
    can_prove_absence = True

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.YOUTUBE_API_KEY

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key:
            raise CatalogueError(
                "YOUTUBE_API_KEY is not set; configure it or use CATALOGUE_PROVIDER=scrape"
            )
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - httpx ships with fastapi
            raise CatalogueError("The 'httpx' package is not installed") from exc

        async with httpx.AsyncClient(timeout=settings.CATALOGUE_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{_API}/{path}", params={**params, "key": self._api_key}
            )
        if response.status_code == 403:
            # 403 covers both "bad key" and "quota spent"; the reason string is
            # the only thing that separates them, and they need opposite
            # responses from the caller.
            body = response.text.lower()
            if "quota" in body:
                raise QuotaExceededError("YouTube Data API quota exhausted for today")
            raise CatalogueError(f"YouTube API rejected the request: {response.text[:200]}")
        if response.status_code != 200:
            raise CatalogueError(
                f"YouTube API returned {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    async def search(self, query: str, *, limit: int = 10) -> list[str]:
        payload = await self._get(
            "search",
            {
                "part": "id",
                "q": query,
                "type": "video",
                "maxResults": min(limit, 50),
                # Ask upstream for what we would otherwise have to filter out.
                "relevanceLanguage": settings.CATALOGUE_LANGUAGE,
                "videoEmbeddable": "true",
                "safeSearch": "strict",
            },
        )
        return [
            item["id"]["videoId"]
            for item in payload.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

    async def lookup(self, video_ids: Sequence[str]) -> list[VideoRecord]:
        ids = list(dict.fromkeys(video_ids))  # de-dupe, preserve order
        found: dict[str, VideoRecord] = {}
        for start in range(0, len(ids), self.lookup_batch_size):
            batch = ids[start : start + self.lookup_batch_size]
            payload = await self._get(
                "videos",
                {"part": "snippet,contentDetails,status,statistics", "id": ",".join(batch)},
            )
            for item in payload.get("items", []):
                record = _to_record(item)
                found[record.video_id] = record

        # An id the API did not return no longer exists (deleted or private).
        # Reporting it as unavailable rather than dropping it is the whole
        # point of the health check.
        return [
            found.get(vid, VideoRecord(video_id=vid, title="", channel="",
                                       duration_hours=0.0, is_available=False))
            for vid in ids
        ]


def _to_record(item: dict[str, Any]) -> VideoRecord:
    snippet = item.get("snippet", {})
    status = item.get("status", {})
    stats = item.get("statistics", {})
    views = stats.get("viewCount")
    return VideoRecord(
        video_id=item["id"],
        title=snippet.get("title", ""),
        channel=snippet.get("channelTitle", ""),
        duration_hours=parse_duration_hours(item.get("contentDetails", {}).get("duration", "")),
        description=(snippet.get("description") or "").strip()[:1000],
        language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
        is_available=status.get("privacyStatus") == "public" and status.get("embeddable", True),
        view_count=int(views) if views is not None else None,
    )

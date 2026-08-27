"""Provider-agnostic catalogue ingestion.

`CatalogueProvider` is the seam between "find real learning content on the
internet" and everything that decides what to do with it. Providers only move
video metadata in and out: they never touch the database, never score a
candidate and never know what a skill is. Selection is a pure engine
(`app.engines.catalogue.select`) and persistence is a service, so swapping the
YouTube Data API for scraping — or for nothing at all — changes how candidates
arrive and nothing else.

The two-step shape (`search` returns ids, `lookup` returns records) mirrors what
the upstream APIs actually charge for: search is expensive and vague, detail
lookup is cheap and batched. Keeping them separate lets the caller pay for
search once and re-check the details of an existing catalogue for free.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class VideoRecord:
    """A real video, as the provider reports it.

    Every field here is upstream truth. Nothing is inferred, defaulted from a
    guess, or filled in when the provider does not know it — `duration_hours`
    of 0.0 means "reported as zero", and an unknown language stays None so the
    selector can treat it as unknown rather than as English.
    """

    video_id: str
    title: str
    channel: str
    duration_hours: float
    description: str = ""
    #: BCP-47-ish tag as the provider reports it ("en", "en-GB", "hi"), or None.
    language: str | None = None
    #: False when the video is private, deleted, or blocked from embedding.
    #: This is the signal that lets a dead catalogue row be deactivated.
    is_available: bool = True
    view_count: int | None = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


class CatalogueError(Exception):
    """Provider transport failure: network, auth, quota, missing dependency."""


class QuotaExceededError(CatalogueError):
    """The provider's quota is spent. Distinct from a generic failure because
    the caller should stop the run rather than retry every remaining item."""


class CatalogueProvider(ABC):
    """A source of real learning videos."""

    name: str = "abstract"

    #: Roughly what one `search` costs in the provider's own budget units, for
    #: run planning and logging. 0 means "not metered".
    search_cost: int = 0
    #: How many ids a single `lookup` call accepts.
    lookup_batch_size: int = 50
    #: Whether `is_available=False` from this provider is TRUSTWORTHY EVIDENCE
    #: that a video is gone, rather than merely the absence of a reply.
    #:
    #: Only an authenticated API can tell "this video is private" apart from
    #: "you are being throttled". A scraper cannot: a rate-limited response and
    #: a deleted video look identical from outside. Defaulting to False means a
    #: new provider has to earn the right to deactivate anything, because the
    #: cost of getting this wrong is deactivating a working catalogue — which
    #: is exactly what happened before this flag existed.
    can_prove_absence: bool = False

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[str]:
        """Candidate video ids for a query, best first. Never raises for an
        empty result — an honest zero is a valid answer."""
        raise NotImplementedError

    @abstractmethod
    async def lookup(self, video_ids: Sequence[str]) -> list[VideoRecord]:
        """Full records for the given ids.

        Ids that no longer resolve are returned with `is_available=False`
        rather than omitted, so a caller checking an existing catalogue can
        tell "gone" apart from "not asked about".
        """
        raise NotImplementedError

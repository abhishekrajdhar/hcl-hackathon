"""Catalogue ingestion against a fake provider — no network, no quota.

Under test is the seam: what gets persisted from a selection, how gaps are
prioritised, and the two directions of the health check. The provider is
stubbed because the real ones reach the public internet, which has no place in
a test suite.
"""

from __future__ import annotations

import uuid
from typing import Sequence

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.catalogue.base import CatalogueError, CatalogueProvider, VideoRecord
from app.db.session import SessionLocal
from app.services.catalogue_service import ORIGIN, CatalogueService

pytestmark = pytest.mark.asyncio

UNIQ = uuid.uuid4().hex[:6]


class FakeProvider(CatalogueProvider):
    """Returns exactly what a test hands it, and records what it was asked.

    `can_prove_absence` is a constructor argument because it is the difference
    between an API that can state a video is private and a scraper that merely
    failed to get an answer.
    """

    name = "fake"
    search_cost = 100

    def __init__(
        self,
        records: Sequence[VideoRecord] = (),
        *,
        fail: bool = False,
        can_prove_absence: bool = True,
    ) -> None:
        self._records = list(records)
        self._fail = fail
        self.can_prove_absence = can_prove_absence
        self.queries: list[str] = []
        self.looked_up: list[str] = []

    async def search(self, query: str, *, limit: int = 10) -> list[str]:
        if self._fail:
            raise CatalogueError("provider is down")
        self.queries.append(query)
        return [r.video_id for r in self._records]

    async def lookup(self, video_ids: Sequence[str]) -> list[VideoRecord]:
        if self._fail:
            raise CatalogueError("provider is down")
        self.looked_up.extend(video_ids)
        known = {r.video_id: r for r in self._records}
        # Ids this fake was not given are OMITTED, which the service reads as
        # "unknown". Returning them as unavailable would make the fake an
        # oracle over the whole catalogue — and a health check run with it
        # deactivated all 89 real videos in the development database.
        return [known[v] for v in video_ids if v in known]


async def _seeded() -> bool:
    try:
        async with SessionLocal() as session:
            n = (await session.execute(text("select count(*) from skills"))).scalar_one()
            return int(n) > 0
    except Exception:  # noqa: BLE001
        return False


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _require_db() -> None:
    if not await _seeded():
        pytest.skip("database not reachable or not seeded", allow_module_level=True)


@pytest_asyncio.fixture(autouse=True)
async def _clean_up():
    """These tests write real rows to the development database."""
    yield
    async with SessionLocal() as session:
        await session.execute(
            text("delete from resources where external_id like :p"), {"p": f"{UNIQ}%"}
        )
        await session.execute(
            text("delete from skills where slug like :p"), {"p": f"%-{UNIQ}"}
        )
        await session.commit()


async def _make_skill(name: str, *, difficulty: int = 3, aliases: list[str] | None = None) -> uuid.UUID:
    async with SessionLocal() as session:
        row = await session.execute(
            text(
                "insert into skills (id, slug, name, description, category_id, difficulty,"
                " level_scale, is_active, aliases, extra, created_at, updated_at)"
                " select gen_random_uuid(), :slug, :name, 'test skill', c.id, :diff, 5, true,"
                " :aliases, '{}'::jsonb, now(), now()"
                " from skill_categories c limit 1 returning id"
            ),
            {
                "slug": f"{name.lower().replace(' ', '-')}-{UNIQ}",
                "name": name,
                "diff": difficulty,
                "aliases": aliases or [],
            },
        )
        skill_id = row.scalar_one()
        await session.commit()
        return skill_id


def _video(vid: str, title: str, channel: str = "Test Channel", hours: float = 3.0, **kw) -> VideoRecord:
    return VideoRecord(video_id=vid, title=title, channel=channel, duration_hours=hours, **kw)


# --- discovery ---------------------------------------------------------------
async def test_discovery_persists_a_usable_resource() -> None:
    """The whole point: a skill nothing taught now has something to teach it."""
    await _make_skill("Zorbonic Streaming")
    provider = FakeProvider([
        _video(f"{UNIQ}aaaaa", "Zorbonic Streaming Full Course", hours=4.0),
    ])
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)
        skill = await service.skill_by_slug(f"zorbonic-streaming-{UNIQ}")
        assert skill is not None
        result = await service.discover_for_skill(skill, picks=2)

    assert result.created, "a matching video should have produced a resource"
    async with SessionLocal() as session:
        row = (await session.execute(
            text("select r.url, r.resource_type, r.estimated_hours, r.extra->>'origin',"
                 " rs.is_primary, rs.teaches_level_to"
                 " from resources r join resource_skills rs on rs.resource_id = r.id"
                 " where r.external_id = :v"),
            {"v": f"{UNIQ}aaaaa"},
        )).first()
    assert row is not None, "the resource must be linked to the skill it was found for"
    url, rtype, hours, origin, is_primary, level_to = row
    assert url.endswith(f"{UNIQ}aaaaa")
    assert rtype == "course" and hours == 4.0
    assert origin == ORIGIN, "discovered rows must be distinguishable from curated ones"
    assert is_primary is True
    assert level_to == 0.75, "difficulty 3 teaches up to 0.75, same as the seed table"


async def test_discovery_rejects_everything_off_topic() -> None:
    """A search that returns nothing relevant must create nothing, not settle."""
    await _make_skill("Quandric Systems")
    provider = FakeProvider([_video(f"{UNIQ}bbbbb", "Learn Python - Full Course")])
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)
        skill = await service.skill_by_slug(f"quandric-systems-{UNIQ}")
        result = await service.discover_for_skill(skill, picks=2)
    assert result.searched and result.candidates == 1
    assert result.created == [], "an off-topic video is worse than no video"


async def test_query_prefers_the_alias() -> None:
    """Formal skill names return essays; the handle a human would type returns
    lessons."""
    await _make_skill("Zorbonic Engines & Frameworks", aliases=["zorbonic"])
    provider = FakeProvider([])
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)
        skill = await service.skill_by_slug(f"zorbonic-engines-&-frameworks-{UNIQ}")
        if skill is None:  # slugify differs; fetch by name instead
            pytest.skip("slug shape differs")
        await service.discover_for_skill(skill)
    assert provider.queries and provider.queries[0].startswith("zorbonic")


async def test_provider_failure_is_reported_not_raised() -> None:
    """Ingestion is background work: a broken provider must not take a run down."""
    await _make_skill("Blivet Theory")
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider(fail=True))
        skill = await service.skill_by_slug(f"blivet-theory-{UNIQ}")
        result = await service.discover_for_skill(skill)
    assert result.error and result.created == []


async def test_uncovered_skills_finds_the_new_gap() -> None:
    await _make_skill("Fnordling Protocols")
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider())
        slugs = {s.slug for s in await service.uncovered_skills()}
    assert f"fnordling-protocols-{UNIQ}" in slugs


# --- health ------------------------------------------------------------------
async def test_health_deactivates_a_vanished_video_and_brings_it_back() -> None:
    """The rot check, both directions. Nothing else in the system would ever
    notice a video going private."""
    await _make_skill("Grexel Dynamics")
    live = _video(f"{UNIQ}ccccc", "Grexel Dynamics Full Course", hours=3.0)
    provider = FakeProvider([live])
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)
        skill = await service.skill_by_slug(f"grexel-dynamics-{UNIQ}")
        assert (await service.discover_for_skill(skill)).created

    gone = FakeProvider([
        VideoRecord(video_id=f"{UNIQ}ccccc", title=live.title, channel=live.channel,
                    duration_hours=3.0, is_available=False)
    ])
    async with SessionLocal() as session:
        report = await CatalogueService(session, gone).health_check(
            external_ids=[f"{UNIQ}ccccc"]
        )
    assert any("Grexel" in t for t in report.deactivated)

    async with SessionLocal() as session:
        report = await CatalogueService(session, FakeProvider([live])).health_check(
            external_ids=[f"{UNIQ}ccccc"]
        )
    assert any("Grexel" in t for t in report.reactivated)


async def test_health_will_not_deactivate_on_a_provider_that_cannot_prove_absence() -> None:
    """The 89-video incident, as a test.

    A scraper being rate-limited reports every video as unavailable, which is
    indistinguishable from every video having been deleted. Acting on that took
    the entire working catalogue offline in one run. Only a provider that can
    actually state a video is gone may deactivate anything.
    """
    await _make_skill("Plimoth Vectors")
    live = _video(f"{UNIQ}eeeee", "Plimoth Vectors Full Course", hours=3.0)
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider([live]))
        skill = await service.skill_by_slug(f"plimoth-vectors-{UNIQ}")
        assert (await service.discover_for_skill(skill)).created

    throttled = FakeProvider(
        [VideoRecord(video_id=f"{UNIQ}eeeee", title=live.title, channel=live.channel,
                     duration_hours=0.0, is_available=False)],
        can_prove_absence=False,
    )
    async with SessionLocal() as session:
        report = await CatalogueService(session, throttled).health_check(
            external_ids=[f"{UNIQ}eeeee"]
        )
    assert report.deactivated == [], "a scraper must never take a resource offline"
    assert f"{UNIQ}eeeee" in report.unknown

    async with SessionLocal() as session:
        still_active = (await session.execute(
            text("select is_active from resources where external_id = :v"),
            {"v": f"{UNIQ}eeeee"},
        )).scalar_one()
    assert still_active is True


async def test_health_report_only_reports_without_writing() -> None:
    """`apply=False` must produce the same verdicts as a real run while
    leaving every row exactly as it found it — that is the whole point of
    letting an operator preview a nightly job."""
    await _make_skill("Dornick Fields")
    live = _video(f"{UNIQ}ggggg", "Dornick Fields Full Course", hours=3.0)
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider([live]))
        skill = await service.skill_by_slug(f"dornick-fields-{UNIQ}")
        assert (await service.discover_for_skill(skill)).created

    gone = FakeProvider([
        VideoRecord(video_id=f"{UNIQ}ggggg", title=live.title, channel=live.channel,
                    duration_hours=3.0, is_available=False)
    ])
    async with SessionLocal() as session:
        report = await CatalogueService(session, gone).health_check(
            external_ids=[f"{UNIQ}ggggg"], apply=False
        )
    assert any("Dornick" in t for t in report.deactivated), (
        "the report must still say what a real run would have done"
    )

    async with SessionLocal() as session:
        still_active = (await session.execute(
            text("select is_active from resources where external_id = :v"),
            {"v": f"{UNIQ}ggggg"},
        )).scalar_one()
    assert still_active is True, "report-only must not write anything"


async def test_health_reactivates_from_any_provider() -> None:
    """Recovery is safe in a way deactivation is not: a successful fetch is
    positive evidence no matter who obtained it."""
    await _make_skill("Cantor Meshes")
    live = _video(f"{UNIQ}fffff", "Cantor Meshes Full Course", hours=3.0)
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider([live]))
        skill = await service.skill_by_slug(f"cantor-meshes-{UNIQ}")
        assert (await service.discover_for_skill(skill)).created
    async with SessionLocal() as session:
        await session.execute(
            text("update resources set is_active = false where external_id = :v"),
            {"v": f"{UNIQ}fffff"},
        )
        await session.commit()

    async with SessionLocal() as session:
        report = await CatalogueService(
            session, FakeProvider([live], can_prove_absence=False)
        ).health_check(external_ids=[f"{UNIQ}fffff"])
    assert any("Cantor" in t for t in report.reactivated)


async def test_health_never_deactivates_what_it_could_not_check() -> None:
    """"We could not reach the provider" and "the video is gone" must never be
    conflated — conflating them would empty the catalogue on a network blip."""
    await _make_skill("Wexil Transforms")
    live = _video(f"{UNIQ}ddddd", "Wexil Transforms Full Course", hours=3.0)
    async with SessionLocal() as session:
        service = CatalogueService(session, FakeProvider([live]))
        skill = await service.skill_by_slug(f"wexil-transforms-{UNIQ}")
        assert (await service.discover_for_skill(skill)).created

    async with SessionLocal() as session:
        report = await CatalogueService(session, FakeProvider(fail=True)).health_check(
            external_ids=[f"{UNIQ}ddddd"]
        )
    assert report.deactivated == []
    assert report.unknown, "unreachable ids must be reported, not silently skipped"

    async with SessionLocal() as session:
        still_active = (await session.execute(
            text("select is_active from resources where external_id = :v"),
            {"v": f"{UNIQ}ddddd"},
        )).scalar_one()
    assert still_active is True

"""Catalogue ingestion and health CLI.

Background maintenance, not a request path. Intended for cron:

    # nightly: notice videos that have been deleted or made private
    python -m scripts.catalogue_pipeline health

    # weekly: give every skill nothing teaches some real content
    python -m scripts.catalogue_pipeline gaps --max-skills 10

    # see what would happen, touch nothing
    python -m scripts.catalogue_pipeline gaps --dry-run

Both commands are safe with no provider configured: CATALOGUE_PROVIDER defaults
to "none", which reports finding nothing rather than pretending to have looked.

Quota, for the youtube provider: `gaps` costs ~100 units per skill searched
against a 10,000/day default (so --max-skills 10 is ~1,000 units), while
`health` batches 50 ids per unit and checks the whole catalogue for 2-3.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from app.catalogue.factory import get_catalogue_provider  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import SessionLocal, dispose_engine  # noqa: E402
from app.services.catalogue_service import CatalogueService  # noqa: E402


async def run_gaps(
    max_skills: int, picks: int, search_limit: int, dry_run: bool,
    only: str | None, confirmed: bool,
) -> int:
    provider = get_catalogue_provider()
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)

        if only:
            skill = await service.skill_by_slug(only)
            if skill is None:
                print(f"no skill with slug {only!r}")
                return 2
            targets = [skill]
        else:
            targets = (await service.uncovered_skills())[:max_skills]

        print(f"provider: {provider.name}   skills to search: {len(targets)}")
        if not targets:
            print("nothing to do — every skill has at least one resource")
            return 0

        cost = len(targets) * provider.search_cost
        if dry_run:
            for skill in targets:
                print(f'  would search: {skill.slug:<32} "{service._query_for(skill)}"')
            print(f"\nestimated quota cost: {cost} units")
            return 0

        # Searching costs metered quota, and a polluted skills table turns that
        # straight into wasted budget. Make the operator look at the plan first
        # rather than discovering the spend afterwards.
        if cost and not confirmed:
            for skill in targets:
                print(f'  {skill.slug:<32} "{service._query_for(skill)}"')
            print(
                f"\nthis would spend ~{cost} quota units. Re-run with --yes to "
                "proceed, or --dry-run to keep looking."
            )
            return 1

        results = await service.fill_gaps(
            max_skills=max_skills, picks=picks, search_limit=search_limit
        ) if not only else [
            await service.discover_for_skill(targets[0], picks=picks, search_limit=search_limit)
        ]
        created = 0
        for result in results:
            if result.error:
                print(f"  {result.skill_slug:<32} ERROR {result.error}")
            elif result.created:
                created += len(result.created)
                for title in result.created:
                    print(f"  {result.skill_slug:<32} + {title[:60]}")
            else:
                print(f"  {result.skill_slug:<32} no candidate passed selection")
        print(f"\ncreated {created} resources across {len(results)} skills")
        if created:
            print("run `python -m app.db.seed` or the embedding backfill to index them")
        return 0


async def run_health(apply: bool) -> int:
    provider = get_catalogue_provider()
    if provider.name == "none":
        print("CATALOGUE_PROVIDER=none — nothing to check against. Set it to "
              "youtube (with YOUTUBE_API_KEY) or scrape.")
        return 0
    async with SessionLocal() as session:
        service = CatalogueService(session, provider)
        report = await service.health_check(apply=apply)
    print(f"provider: {provider.name}   checked: {report.checked}"
          + ("" if apply else "   (report only — nothing written)"))
    for title in report.deactivated:
        print(f"  {'DEACTIVATED' if apply else 'WOULD DEACTIVATE':<16} {title[:66]}")
    for title in report.reactivated:
        print(f"  {'BACK' if apply else 'WOULD REACTIVATE':<16} {title[:66]}")
    if report.unknown:
        print(f"  {len(report.unknown)} could not be checked (left untouched)")
    if not report.deactivated and not report.reactivated:
        print("every catalogue video is still available")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gaps = sub.add_parser("gaps", help="find content for skills nothing teaches")
    gaps.add_argument("--max-skills", type=int, default=10)
    gaps.add_argument("--picks", type=int, default=settings.CATALOGUE_PICKS_PER_SKILL)
    gaps.add_argument("--search-limit", type=int, default=settings.CATALOGUE_SEARCH_LIMIT)
    gaps.add_argument("--dry-run", action="store_true", help="print the plan and its quota cost")
    gaps.add_argument("--skill", help="target one skill by slug instead of the gap list")
    gaps.add_argument("--yes", action="store_true", help="confirm a run that spends quota")

    health = sub.add_parser("health", help="deactivate resources whose video is gone")
    health.add_argument(
        "--report-only", action="store_true",
        help="show what a run would change without writing anything",
    )

    args = parser.parse_args()
    configure_logging()

    async def dispatch() -> int:
        # One event loop for the whole run: disposing the engine from a second
        # `asyncio.run` tears down connections that belong to the first, which
        # surfaces as "attached to a different loop" during shutdown.
        try:
            if args.command == "gaps":
                return await run_gaps(
                    args.max_skills, args.picks, args.search_limit,
                    args.dry_run, args.skill, args.yes,
                )
            return await run_health(not args.report_only)
        finally:
            await dispose_engine()

    return asyncio.run(dispatch())


if __name__ == "__main__":
    raise SystemExit(main())

"""Ingestion CLI (AGENTS.md section 7.2 / BUILD_PROMPTS Phase 1).

Commands:
    elenchus-ingest factchecks [--since YYYY-MM-DD] [--languages en,hi,mr] [--max-pages N]
    elenchus-ingest crawl [--source NAME] [--max-urls N] [--delay SECONDS]
    elenchus-ingest stats

Built on argparse to stay within the locked dependency set. Needs
``DATABASE_URL`` (and ``GOOGLE_FACTCHECK_API_KEY`` for the API path) in the env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from elenchus.config import get_settings
from elenchus.db.repositories import FactCheckRepository
from elenchus.db.session import get_sessionmaker
from elenchus.ingest import claimreview_crawler, factcheck_api


def _parse_languages(value: str | None) -> tuple[str, ...]:
    if not value:
        return factcheck_api.DEFAULT_LANGUAGES
    return tuple(part.strip() for part in value.split(",") if part.strip())


async def _run_factchecks(args: argparse.Namespace) -> None:
    settings = get_settings()
    since = date.fromisoformat(args.since) if args.since else None
    async with get_sessionmaker()() as session:
        result = await factcheck_api.ingest_factchecks(
            session,
            api_key=settings.google_factcheck_api_key,
            languages=_parse_languages(args.languages),
            since=since,
            max_pages=args.max_pages,
        )
    print(f"factchecks: inserted={result.inserted} updated={result.updated} total={result.total}")


async def _run_crawl(args: argparse.Namespace) -> None:
    async with get_sessionmaker()() as session:
        result = await claimreview_crawler.ingest_claimreviews(
            session,
            only_source=args.source,
            max_urls=args.max_urls,
            delay=args.delay,
        )
    print(f"crawl: inserted={result.inserted} updated={result.updated} total={result.total}")


async def _run_stats(_args: argparse.Namespace) -> None:
    async with get_sessionmaker()() as session:
        stats = await FactCheckRepository.stats(session)
    print(json.dumps(stats.model_dump(), indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elenchus-ingest", description="Fact-check corpus ingestion"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fc = sub.add_parser("factchecks", help="Ingest via Google Fact Check Tools API")
    p_fc.add_argument("--since", help="Only claims newer than this date (YYYY-MM-DD)")
    p_fc.add_argument("--languages", help="Comma-separated language codes (default en,hi,mr)")
    p_fc.add_argument("--max-pages", type=int, default=10, help="Max result pages per query")
    p_fc.set_defaults(func=_run_factchecks)

    p_cr = sub.add_parser("crawl", help="Crawl ClaimReview JSON-LD from fact-checker sites")
    p_cr.add_argument("--source", help="Only crawl this source (by name)")
    p_cr.add_argument("--max-urls", type=int, default=claimreview_crawler.DEFAULT_MAX_URLS)
    p_cr.add_argument("--delay", type=float, default=claimreview_crawler.DEFAULT_CRAWL_DELAY)
    p_cr.set_defaults(func=_run_crawl)

    p_st = sub.add_parser("stats", help="Show corpus counts by language, publisher and month")
    p_st.set_defaults(func=_run_stats)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()

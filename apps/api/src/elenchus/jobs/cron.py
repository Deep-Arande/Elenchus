"""Cron job definitions.

- ``sample_cron``: a no-op retained from Phase 0 (used by tests).
- ``daily_ingest``: Phase 1 daily incremental fact-check ingestion (AGENTS.md
  7.2). Runs the API ingester (claims newer than yesterday) and the ClaimReview
  crawler. Skips gracefully when credentials/DB are not configured.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from elenchus.config import get_settings
from elenchus.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


async def sample_cron(ctx: dict[str, Any]) -> str:
    """No-op scheduled task. Returns a marker string for tests."""
    return "sample_cron ran"


async def daily_ingest(ctx: dict[str, Any]) -> str:
    """Incremental corpus refresh: API (since yesterday) + ClaimReview crawl."""
    from elenchus.ingest import claimreview_crawler, factcheck_api

    settings = get_settings()
    if not settings.database_url:
        logger.warning("daily_ingest skipped: DATABASE_URL not configured")
        return "skipped: no database"

    since = date.today() - timedelta(days=2)
    summary: list[str] = []

    async with get_sessionmaker()() as session:
        if settings.google_factcheck_api_key:
            api_result = await factcheck_api.ingest_factchecks(
                session, api_key=settings.google_factcheck_api_key, since=since
            )
            summary.append(f"api inserted={api_result.inserted} updated={api_result.updated}")
        else:
            logger.warning("daily_ingest: GOOGLE_FACTCHECK_API_KEY missing, skipping API path")

        crawl_result = await claimreview_crawler.ingest_claimreviews(session)
        summary.append(f"crawl inserted={crawl_result.inserted} updated={crawl_result.updated}")

    return "; ".join(summary)

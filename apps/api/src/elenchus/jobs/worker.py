"""arq worker entrypoint.

Run with: ``uv run arq elenchus.jobs.worker.WorkerSettings``

Phase 0 ships one sample job and one sample cron (both no-ops) to prove the
worker boots, connects to Redis and schedules work. Real jobs — ingestion,
check execution, upload processing — arrive in later phases.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from elenchus.config import get_settings
from elenchus.jobs.cron import daily_ingest


async def sample_job(ctx: dict[str, Any], message: str = "ping") -> str:
    """A trivial no-op job used to verify enqueue/execute round-trips."""
    return f"sample_job received: {message}"


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook (placeholder for DB/engine wiring in later phases)."""
    return None


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook."""
    return None


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    """arq worker configuration."""

    functions = [sample_job]
    cron_jobs = [
        # Daily incremental fact-check corpus ingestion at 03:00 (AGENTS.md 7.2).
        cron(daily_ingest, hour=3, minute=0, run_at_startup=False),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()

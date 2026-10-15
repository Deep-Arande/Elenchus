"""Tests for the arq worker: sample job and sample cron (no external calls)."""

from __future__ import annotations

from elenchus.jobs.cron import sample_cron
from elenchus.jobs.worker import WorkerSettings, sample_job


async def test_sample_job_runs() -> None:
    result = await sample_job({}, "hello")
    assert result == "sample_job received: hello"


async def test_sample_cron_runs() -> None:
    result = await sample_cron({})
    assert result == "sample_cron ran"


def test_worker_settings_registered() -> None:
    # The job is registered and at least one cron job is scheduled.
    assert sample_job in WorkerSettings.functions
    assert len(WorkerSettings.cron_jobs) >= 1

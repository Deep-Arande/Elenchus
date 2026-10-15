"""Shared networking helpers for ingestion: polite client + retry/backoff.

All outbound requests carry a clear User-Agent (AGENTS.md section 7.2). Retries
use exponential backoff with jitter on transient failures (timeouts, connection
errors, 429 and 5xx).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx

USER_AGENT = "ElenchusBot/0.1 (+https://elenchus.app; research demo; contact: admin)"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def make_client(timeout: float = 20.0, **kwargs: object) -> httpx.AsyncClient:
    """Create an AsyncClient with the polite default User-Agent and timeout."""
    headers = {"User-Agent": USER_AGENT}
    return httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True, **kwargs)  # type: ignore[arg-type]


class RetryableHTTPError(Exception):
    """Raised for an HTTP status that should be retried."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable status {status_code}")
        self.status_code = status_code


async def async_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
) -> T:
    """Run ``fn`` with exponential backoff + jitter on transient errors.

    Retries on ``httpx.TransportError`` and ``RetryableHTTPError``. Other
    exceptions propagate immediately. The last attempt's error is re-raised.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except (httpx.TransportError, RetryableHTTPError) as exc:
            last_exc = exc
            if attempt == attempts - 1:
                break
            delay = min(max_delay, base_delay * (2**attempt))
            delay += random.uniform(0, delay * 0.25)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def raise_for_retryable(response: httpx.Response) -> None:
    """Translate a retryable status code into ``RetryableHTTPError``."""
    if response.status_code in _RETRYABLE_STATUS:
        raise RetryableHTTPError(response.status_code)

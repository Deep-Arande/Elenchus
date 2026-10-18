"""Search layer for the prototype: web search + page fetch.

Uses Firecrawl when ``FIRECRAWL_API_KEY`` is set, otherwise deterministic mock
results so the flow is demoable without keys (``settings.search_mock``).

Mock search and mock fetch are coordinated: search records a synthetic page per
hit so that fetched text contains sentences relevant to the query, which lets
the (mock) evidence extractor pull real, verifiable quotes.

NOTE: the Firecrawl calls here are best-effort for the throwaway prototype; the
real build implements the full two-stage provider in ``search/firecrawl.py`` and
verifies exact parameter names against the official docs.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from elenchus.config import get_settings

logger = logging.getLogger("elenchus.proto.search")

FIRECRAWL_TIMEOUT = 20.0  # seconds per Firecrawl call
FIRECRAWL_ATTEMPTS = 3  # total tries for transient failures

Reason = Literal["auth", "quota", "rate_limited", "timeout", "server", "network", "unknown"]
# Reasons worth retrying (transient). auth/quota are not — retrying won't help.
_RETRYABLE: set[Reason] = {"rate_limited", "server", "timeout", "network"}

_FRIENDLY: dict[Reason, str] = {
    "auth": "invalid or missing Firecrawl API key",
    "quota": "Firecrawl quota/credits exhausted",
    "rate_limited": "Firecrawl rate limit hit",
    "timeout": "Firecrawl request timed out",
    "server": "Firecrawl service error",
    "network": "could not reach Firecrawl",
    "unknown": "search provider error",
}


class SearchError(Exception):
    """A classified Firecrawl failure the pipeline can turn into a trace warning."""

    def __init__(self, reason: Reason, detail: str = "") -> None:
        self.reason: Reason = reason
        self.detail = detail
        super().__init__(f"{_FRIENDLY[reason]}" + (f": {detail}" if detail else ""))

    @property
    def friendly(self) -> str:
        return _FRIENDLY[self.reason]


def _classify(exc: BaseException) -> Reason:
    """Map a raw Firecrawl/transport exception to a Reason."""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    text = str(exc).lower()
    if any(k in text for k in ("unauthorized", "invalid token", "401", "forbidden", "403")):
        return "auth"
    if any(k in text for k in ("payment", "quota", "credit", "402", "insufficient")):
        return "quota"
    if any(k in text for k in ("rate limit", "429", "too many requests")):
        return "rate_limited"
    if any(k in text for k in ("timeout", "timed out", "deadline")):
        return "timeout"
    if any(k in text for k in ("500", "502", "503", "504", "server error", "unavailable")):
        return "server"
    if any(k in text for k in ("connection", "network", "resolve", "dns", "ssl", "econn")):
        return "network"
    return "unknown"


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str = ""
    domain: str | None = None


# Coordinated mock page store: url -> synthetic page text (mock mode only).
_MOCK_PAGES: dict[str, str] = {}

_MOCK_DOMAINS = [
    ("factcheck.example.org", "Example FactCheck"),
    ("news.example.com", "Example News"),
    ("research.example.edu", "Example Research"),
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "claim"


async def search(query: str, *, limit: int = 3) -> list[SearchHit]:
    """Search the web. Raises SearchError on a classified provider failure."""
    if get_settings().search_mock:
        return _mock_search(query, limit)
    hits = await _firecrawl_search(query, limit)
    logger.info("search ok: %d hit(s) for %r", len(hits), query[:80])
    return hits


async def fetch(url: str) -> str:
    """Fetch a page as text. Raises SearchError on a classified provider failure."""
    if get_settings().search_mock:
        return _MOCK_PAGES.get(url, f"No cached content for {url}.")
    text = await _firecrawl_fetch(url)
    logger.info("fetch ok: %d chars from %s", len(text), url)
    return text


# --------------------------------------------------------------------------- #
# Firecrawl (best-effort, exercised only with a real key)
# --------------------------------------------------------------------------- #
@lru_cache
def _fc():  # cached Firecrawl v4 client
    from firecrawl import Firecrawl

    return Firecrawl(api_key=get_settings().firecrawl_api_key)


async def _call(op: str, fn: Callable[[], object]) -> object:
    """Run a blocking Firecrawl call with a timeout + retry on transient errors.

    Raises SearchError (classified) when it ultimately fails.
    """
    last: Reason = "unknown"
    detail = ""
    for attempt in range(FIRECRAWL_ATTEMPTS):
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn), timeout=FIRECRAWL_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - classified and re-raised below
            last = _classify(exc)
            detail = str(exc)[:200]
            if last not in _RETRYABLE or attempt == FIRECRAWL_ATTEMPTS - 1:
                logger.warning("firecrawl %s failed (%s): %s", op, last, detail)
                raise SearchError(last, detail) from exc
            wait = 0.8 * (2**attempt)
            logger.info(
                "firecrawl %s transient (%s), retry %d/%d in %.1fs",
                op,
                last,
                attempt + 1,
                FIRECRAWL_ATTEMPTS,
                wait,
            )
            await asyncio.sleep(wait)
    raise SearchError(last, detail)


async def _firecrawl_search(query: str, limit: int) -> list[SearchHit]:
    data = await _call("search", lambda: _fc().search(query, limit=limit))
    web = getattr(data, "web", None) or []
    hits: list[SearchHit] = []
    for item in list(web)[:limit]:
        url = getattr(item, "url", None)
        if not url:
            continue
        hits.append(
            SearchHit(
                title=getattr(item, "title", None) or url,
                url=url,
                snippet=getattr(item, "description", None) or "",
                domain=urlparse(url).hostname,
            )
        )
    return hits


async def _firecrawl_fetch(url: str) -> str:
    doc = await _call("scrape", lambda: _fc().scrape(url, formats=["markdown"]))
    return getattr(doc, "markdown", None) or getattr(doc, "html", None) or ""


# --------------------------------------------------------------------------- #
# Deterministic mocks
# --------------------------------------------------------------------------- #
def _mock_search(query: str, limit: int) -> list[SearchHit]:
    slug = _slug(query)
    hits: list[SearchHit] = []
    for i, (domain, pub) in enumerate(_MOCK_DOMAINS[:limit]):
        url = f"https://{domain}/article/{slug}-{i + 1}"
        page = _mock_page(query, pub, i)
        _MOCK_PAGES[url] = page
        hits.append(
            SearchHit(
                title=f"{pub}: a look at “{query[:60]}”",
                url=url,
                snippet=page.split(". ")[0][:160],
                domain=domain,
            )
        )
    return hits


def _mock_page(query: str, publisher: str, i: int) -> str:
    angles = [
        f"Reporting by {publisher} indicates the statement that {query} is consistent "
        "with records reviewed for this article.",
        f"However, {publisher} notes that the claim that {query} is disputed by several "
        "independent experts contacted for comment.",
        f"For context, {publisher} explains that the question of whether {query} depends "
        "on definitions and the time period considered.",
    ]
    return (
        f"{publisher} examined the claim in detail. {angles[i % len(angles)]} "
        "Readers are encouraged to consult the primary sources linked in the piece. "
        "This page is synthetic prototype content for demonstration."
    )

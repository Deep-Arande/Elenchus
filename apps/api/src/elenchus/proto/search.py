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
import re
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import BaseModel

from elenchus.config import get_settings


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
    settings = get_settings()
    if settings.search_mock:
        return _mock_search(query, limit)
    return await _firecrawl_search(query, limit)


async def fetch(url: str) -> str:
    settings = get_settings()
    if settings.search_mock:
        return _MOCK_PAGES.get(url, f"No cached content for {url}.")
    return await _firecrawl_fetch(url)


# --------------------------------------------------------------------------- #
# Firecrawl (best-effort, exercised only with a real key)
# --------------------------------------------------------------------------- #
@lru_cache
def _fc():  # cached Firecrawl v4 client
    from firecrawl import Firecrawl

    return Firecrawl(api_key=get_settings().firecrawl_api_key)


async def _firecrawl_search(query: str, limit: int) -> list[SearchHit]:
    data = await asyncio.to_thread(lambda: _fc().search(query, limit=limit))
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
    doc = await asyncio.to_thread(lambda: _fc().scrape(url, formats=["markdown"]))
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

"""Google Fact Check Tools API ingestion (AGENTS.md section 7.2).

Queries the ``claims:search`` endpoint by seed topics and by Indian
fact-checker publisher sites, across language codes en/hi/mr, pages through
results, normalises into ``FactCheckRecord`` and idempotently upserts.

The response parser (``records_from_claims``) is pure and fixture-tested; the
HTTP client handles paging and retries.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from elenchus.db.repositories import FactCheckRepository, UpsertResult
from elenchus.ingest.net import async_retry, make_client, raise_for_retryable
from elenchus.ingest.schemas import FactCheckRecord, parse_date

logger = logging.getLogger(__name__)

SEARCH_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Seed topics prone to misinformation in the Indian context. Tunable; the CLI
# can override. Kept deliberately broad and neutral.
DEFAULT_SEED_TOPICS: tuple[str, ...] = (
    "vaccine",
    "election",
    "COVID",
    "WhatsApp forward",
    "UNESCO",
    "currency note",
    "Aadhaar",
    "viral video",
    "government scheme",
    "health remedy",
)

# Indian fact-checker publisher sites to query directly.
DEFAULT_PUBLISHER_SITES: tuple[str, ...] = (
    "boomlive.in",
    "altnews.in",
    "factly.in",
    "vishvasnews.com",
    "thequint.com",
    "factcrescendo.com",
    "newschecker.in",
)

DEFAULT_LANGUAGES: tuple[str, ...] = ("en", "hi", "mr")


def records_from_claims(claims: list[dict]) -> list[FactCheckRecord]:
    """Flatten the API ``claims[]`` into one record per ``claimReview``."""
    records: list[FactCheckRecord] = []
    for claim in claims:
        claim_text = (claim.get("text") or "").strip()
        if not claim_text:
            continue
        claimant = claim.get("claimant")
        claim_date = parse_date(claim.get("claimDate"))
        for review in claim.get("claimReview", []):
            review_url = (review.get("url") or "").strip()
            if not review_url:
                continue
            publisher = review.get("publisher") or {}
            records.append(
                FactCheckRecord(
                    claim_text=claim_text,
                    claim_language=review.get("languageCode"),
                    claimant=claimant,
                    claim_date=claim_date,
                    publisher_name=publisher.get("name"),
                    publisher_site=publisher.get("site"),
                    review_url=review_url,
                    review_title=review.get("title"),
                    rating_text=review.get("textualRating"),
                    review_date=parse_date(review.get("reviewDate")),
                    image_url=None,
                    source="gfc_api",
                    raw_jsonld=None,
                )
            )
    return records


class GoogleFactCheckClient:
    """Thin async client over the Fact Check Tools claims:search endpoint."""

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not api_key:
            raise ValueError("GOOGLE_FACTCHECK_API_KEY is required for ingestion")
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> GoogleFactCheckClient:
        if self._client is None:
            self._client = make_client()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def _get_page(self, params: dict[str, str | int]) -> dict:
        assert self._client is not None, "use as an async context manager"
        client = self._client

        async def _do() -> httpx.Response:
            resp = await client.get(SEARCH_URL, params=params)
            raise_for_retryable(resp)
            return resp

        resp = await async_retry(_do)
        resp.raise_for_status()
        return resp.json()

    async def search(
        self,
        *,
        query: str | None = None,
        language_code: str | None = None,
        review_publisher_site_filter: str | None = None,
        max_age_days: int | None = None,
        page_size: int = 50,
        max_pages: int = 20,
    ) -> list[dict]:
        """Page through claims:search and return the raw ``claims[]`` dicts."""
        collected: list[dict] = []
        page_token: str | None = None
        for _ in range(max_pages):
            params: dict[str, str | int] = {"key": self._api_key, "pageSize": page_size}
            if query:
                params["query"] = query
            if language_code:
                params["languageCode"] = language_code
            if review_publisher_site_filter:
                params["reviewPublisherSiteFilter"] = review_publisher_site_filter
            if max_age_days is not None:
                params["maxAgeDays"] = max_age_days
            if page_token:
                params["pageToken"] = page_token

            data = await self._get_page(params)
            collected.extend(data.get("claims", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return collected


def _max_age_days(since: date | None) -> int | None:
    if since is None:
        return None
    return max(1, (date.today() - since).days)


async def ingest_factchecks(
    session: AsyncSession,
    *,
    api_key: str,
    topics: tuple[str, ...] = DEFAULT_SEED_TOPICS,
    publisher_sites: tuple[str, ...] = DEFAULT_PUBLISHER_SITES,
    languages: tuple[str, ...] = DEFAULT_LANGUAGES,
    since: date | None = None,
    max_pages: int = 10,
) -> UpsertResult:
    """Run the full API ingestion and upsert the results. Returns totals."""
    max_age = _max_age_days(since)
    all_records: list[FactCheckRecord] = []

    async with GoogleFactCheckClient(api_key) as client:
        for language in languages:
            for topic in topics:
                claims = await client.search(
                    query=topic, language_code=language, max_age_days=max_age, max_pages=max_pages
                )
                all_records.extend(records_from_claims(claims))
            for site in publisher_sites:
                claims = await client.search(
                    language_code=language,
                    review_publisher_site_filter=site,
                    max_age_days=max_age,
                    max_pages=max_pages,
                )
                all_records.extend(records_from_claims(claims))

    logger.info("fact-check API ingestion collected %d records", len(all_records))
    result = await FactCheckRepository.upsert_many(session, all_records)
    await session.commit()
    return result

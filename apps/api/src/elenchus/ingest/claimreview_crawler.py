"""ClaimReview crawler (AGENTS.md section 7.2).

Reads the fact-checker list in ``sources.yaml``, discovers article URLs from
each site's sitemap/RSS, fetches pages politely (robots.txt, delay, clear
User-Agent) and extracts ClaimReview JSON-LD with ``extruct``. Only metadata
and short claim text are stored — never the full article.

Parsers (``records_from_jsonld``, ``parse_claimreview_html``,
``urls_from_xml``) are pure and fixture-tested; the crawl orchestration handles
IO, robots and politeness.
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import extruct
import httpx
import yaml
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from elenchus.db.repositories import FactCheckRepository, UpsertResult
from elenchus.ingest.net import USER_AGENT, async_retry, make_client, raise_for_retryable
from elenchus.ingest.schemas import FactCheckRecord, parse_date

logger = logging.getLogger(__name__)

SOURCES_PATH = Path(__file__).with_name("sources.yaml")
DEFAULT_CRAWL_DELAY = 1.0  # seconds between requests to one host
DEFAULT_MAX_URLS = 100


class SourceSite(BaseModel):
    name: str
    homepage: str
    rss_or_sitemap: str | None = None
    language: str | None = None
    enabled: bool = True


def load_sources(path: Path = SOURCES_PATH) -> list[SourceSite]:
    """Load and parse the fact-checker site list from YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SourceSite(**entry) for entry in data.get("sources", [])]


# --------------------------------------------------------------------------- #
# Pure parsers
# --------------------------------------------------------------------------- #
def _name_of(obj: object) -> str | None:
    """Pull a name from an author/publisher that may be a str, dict or list."""
    if isinstance(obj, str):
        return obj or None
    if isinstance(obj, dict):
        name = obj.get("name")
        return name if isinstance(name, str) and name else None
    if isinstance(obj, list):
        for element in obj:
            name = _name_of(element)
            if name:
                return name
    return None


def _rating_of(review_rating: object) -> str | None:
    """Extract a textual rating from a reviewRating node."""
    if isinstance(review_rating, list):
        review_rating = review_rating[0] if review_rating else None
    if isinstance(review_rating, dict):
        for key in ("alternateName", "ratingExplanation", "name", "ratingValue"):
            value = review_rating.get(key)
            if value:
                return str(value)
    if isinstance(review_rating, str):
        return review_rating or None
    return None


def iter_claimreviews(items: list) -> Iterator[dict]:
    """Yield ClaimReview nodes from a json-ld list, descending into @graph."""
    for item in items:
        if not isinstance(item, dict):
            continue
        if "@graph" in item and isinstance(item["@graph"], list):
            yield from iter_claimreviews(item["@graph"])
        node_type = item.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any(isinstance(t, str) and t.endswith("ClaimReview") for t in types):
            yield item


def records_from_jsonld(
    items: list,
    *,
    page_url: str,
    fallback_publisher: str | None = None,
    fallback_site: str | None = None,
) -> list[FactCheckRecord]:
    """Map ClaimReview JSON-LD nodes to ``FactCheckRecord``s (metadata only)."""
    records: list[FactCheckRecord] = []
    for node in iter_claimreviews(items):
        claim_text = node.get("claimReviewed")
        if not isinstance(claim_text, str) or not claim_text.strip():
            continue
        url = node.get("url") or page_url
        item_reviewed = node.get("itemReviewed")
        if isinstance(item_reviewed, list):
            item_reviewed = item_reviewed[0] if item_reviewed else {}
        if not isinstance(item_reviewed, dict):
            item_reviewed = {}

        publisher_name = (
            _name_of(node.get("author")) or _name_of(node.get("publisher")) or fallback_publisher
        )
        site = fallback_site or (urlparse(str(url)).hostname or None)

        records.append(
            FactCheckRecord(
                claim_text=claim_text.strip(),
                claim_language=node.get("inLanguage")
                if isinstance(node.get("inLanguage"), str)
                else None,
                claimant=_name_of(item_reviewed.get("author")),
                claim_date=parse_date(item_reviewed.get("datePublished")),
                publisher_name=publisher_name,
                publisher_site=site,
                review_url=str(url),
                review_title=node.get("headline") or node.get("name"),
                rating_text=_rating_of(node.get("reviewRating")),
                review_date=parse_date(node.get("datePublished")),
                image_url=None,
                source="claimreview_crawl",
                raw_jsonld=node,
            )
        )
    return records


def parse_claimreview_html(
    html: str,
    *,
    page_url: str,
    fallback_publisher: str | None = None,
    fallback_site: str | None = None,
) -> list[FactCheckRecord]:
    """Extract ClaimReview JSON-LD from a page's HTML and map to records."""
    extracted = extruct.extract(html, base_url=page_url, syntaxes=["json-ld"], uniform=True)
    items = extracted.get("json-ld", [])
    return records_from_jsonld(
        items,
        page_url=page_url,
        fallback_publisher=fallback_publisher,
        fallback_site=fallback_site,
    )


def urls_from_xml(xml_text: str) -> list[str]:
    """Extract URLs from a sitemap (<loc>) or RSS/Atom (<link>) document."""
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return urls
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1].lower()
        if tag == "loc" and el.text:
            urls.append(el.text.strip())
        elif tag == "link":
            href = el.get("href")
            if href:
                urls.append(href.strip())
            elif el.text and el.text.strip().startswith("http"):
                urls.append(el.text.strip())
    return urls


# --------------------------------------------------------------------------- #
# Crawl orchestration (IO)
# --------------------------------------------------------------------------- #
async def _get_text(client: httpx.AsyncClient, url: str) -> str | None:
    async def _do() -> httpx.Response:
        resp = await client.get(url)
        raise_for_retryable(resp)
        return resp

    try:
        resp = await async_retry(_do)
    except httpx.HTTPError:
        logger.warning("fetch failed: %s", url)
        return None
    if resp.status_code != 200:
        return None
    return resp.text


async def _load_robots(client: httpx.AsyncClient, homepage: str) -> RobotFileParser:
    rp = RobotFileParser()
    parsed = urlparse(homepage)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    text = await _get_text(client, robots_url)
    # A missing/unreachable robots.txt is treated as allow-all: parsing empty
    # lines marks the parser as "checked" with no rules, so can_fetch() returns
    # True (avoids touching the untyped allow_all attribute).
    rp.parse((text or "").splitlines())
    return rp


async def crawl_source(
    session_client: httpx.AsyncClient,
    site: SourceSite,
    *,
    max_urls: int = DEFAULT_MAX_URLS,
    delay: float = DEFAULT_CRAWL_DELAY,
) -> list[FactCheckRecord]:
    """Crawl one fact-checker site, respecting robots.txt and a polite delay."""
    feed_url = site.rss_or_sitemap or site.homepage
    robots = await _load_robots(session_client, site.homepage)

    feed_xml = await _get_text(session_client, feed_url)
    urls = urls_from_xml(feed_xml) if feed_xml else []
    urls = urls[:max_urls]

    records: list[FactCheckRecord] = []
    for url in urls:
        if not robots.can_fetch(USER_AGENT, url):
            logger.info("robots.txt disallows: %s", url)
            continue
        await asyncio.sleep(delay)
        html = await _get_text(session_client, url)
        if not html:
            continue
        records.extend(
            parse_claimreview_html(
                html,
                page_url=url,
                fallback_publisher=site.name,
                fallback_site=urlparse(site.homepage).hostname,
            )
        )
    logger.info("crawled %s: %d records from %d urls", site.name, len(records), len(urls))
    return records


async def ingest_claimreviews(
    session: AsyncSession,
    *,
    only_source: str | None = None,
    max_urls: int = DEFAULT_MAX_URLS,
    delay: float = DEFAULT_CRAWL_DELAY,
) -> UpsertResult:
    """Crawl all enabled sources (or one named source) and upsert the results."""
    sites = [s for s in load_sources() if s.enabled]
    if only_source:
        sites = [s for s in sites if s.name.lower() == only_source.lower()]
        if not sites:
            raise ValueError(f"No enabled source named {only_source!r}")

    all_records: list[FactCheckRecord] = []
    async with make_client() as client:
        for site in sites:
            try:
                all_records.extend(await crawl_source(client, site, max_urls=max_urls, delay=delay))
            except httpx.HTTPError:
                logger.exception("crawl failed for %s", site.name)

    result = await FactCheckRepository.upsert_many(session, all_records)
    await session.commit()
    return result

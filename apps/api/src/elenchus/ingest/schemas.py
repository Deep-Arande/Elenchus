"""Normalised fact-check record shared by both ingestion paths.

Both the Google Fact Check Tools API ingester and the ClaimReview crawler
produce ``FactCheckRecord``s; the repository upserts them. Only metadata and
short claim text are stored — never full articles (AGENTS.md sections 2.6, 7.2).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

FactCheckSource = Literal["gfc_api", "claimreview_crawl"]

_WHITESPACE = re.compile(r"\s+")


def parse_date(value: str | None) -> date | None:
    """Tolerantly parse an ISO date/datetime string to a ``date``."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def normalise_claim_text(text: str) -> str:
    """Normalise claim text for hashing/dedup: NFC, trimmed, collapsed, casefold."""
    text = unicodedata.normalize("NFC", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text.casefold()


def claim_hash(claim_text: str) -> str:
    """Stable SHA-256 of the normalised claim text (dedup key with review_url)."""
    return hashlib.sha256(normalise_claim_text(claim_text).encode("utf-8")).hexdigest()


class FactCheckRecord(BaseModel):
    """One normalised fact-check ready to upsert into ``factchecks``."""

    claim_text: str
    claim_language: str | None = None
    claimant: str | None = None
    claim_date: date | None = None
    publisher_name: str | None = None
    publisher_site: str | None = None
    review_url: str
    review_title: str | None = None
    rating_text: str | None = None
    review_date: date | None = None
    image_url: str | None = None
    source: FactCheckSource
    raw_jsonld: dict | None = Field(default=None)

    @property
    def claim_hash(self) -> str:
        return claim_hash(self.claim_text)

    def to_row(self) -> dict:
        """Column dict for a bulk upsert (includes the computed ``claim_hash``)."""
        return {
            "claim_text": self.claim_text,
            "claim_hash": self.claim_hash,
            "claim_language": self.claim_language,
            "claimant": self.claimant,
            "claim_date": self.claim_date,
            "publisher_name": self.publisher_name,
            "publisher_site": self.publisher_site,
            "review_url": self.review_url,
            "review_title": self.review_title,
            "rating_text": self.rating_text,
            "review_date": self.review_date,
            "image_url": self.image_url,
            "source": self.source,
            "raw_jsonld": self.raw_jsonld,
        }

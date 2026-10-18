"""Tests for the prototype search error classification (no network)."""

from __future__ import annotations

import pytest

from elenchus.proto.search import SearchError, _classify


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Unauthorized: Invalid token - No additional error details", "auth"),
        ("403 Forbidden", "auth"),
        ("402 Payment Required: insufficient credits", "quota"),
        ("429 Too Many Requests", "rate_limited"),
        ("Request timed out after 20s", "timeout"),
        ("503 Service Unavailable", "server"),
        ("Connection refused: could not resolve host", "network"),
        ("something totally unexpected", "unknown"),
    ],
)
def test_classify(message: str, expected: str) -> None:
    assert _classify(Exception(message)) == expected


def test_classify_timeout_error() -> None:
    assert _classify(TimeoutError()) == "timeout"


def test_search_error_friendly() -> None:
    err = SearchError("auth", "bad key")
    assert err.reason == "auth"
    assert "Firecrawl" in err.friendly
    assert "bad key" in str(err)

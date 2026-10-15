"""Tests for the /health endpoint."""

from __future__ import annotations

import httpx

from elenchus import __version__


async def test_health_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "git_sha" in body and body["git_sha"]

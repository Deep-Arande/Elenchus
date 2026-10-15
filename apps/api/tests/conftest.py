"""Shared pytest fixtures.

Phase 0 tests never make external calls (AGENTS.md section 15). The app factory
takes an explicit ``Settings`` so tests run without any ``.env``.
"""

from __future__ import annotations

import httpx
import pytest

from elenchus.config import Settings
from elenchus.main import create_app


@pytest.fixture
def settings() -> Settings:
    # Construct with defaults only; do not read the developer's real .env.
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
async def client(settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

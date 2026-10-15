"""Async database engine and session management.

Runtime data access is SQLAlchemy 2.0 async over psycopg 3 (AGENTS.md section
3). The ``DATABASE_URL`` must use the ``postgresql+psycopg://`` scheme so the
async engine drives psycopg 3 in async mode; ``normalise_async_url`` upgrades a
plain ``postgresql://`` (as copied from the Supabase dashboard) automatically.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from elenchus.config import get_settings


def normalise_async_url(url: str) -> str:
    """Ensure the URL uses the async psycopg 3 driver.

    Supabase hands out ``postgresql://...``; SQLAlchemy's async engine needs
    ``postgresql+psycopg://...``. Leave any explicit ``+driver`` untouched.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily create and cache the process-wide async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            normalise_async_url(settings.database_url),
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Lazily create and cache the async sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session and always close it."""
    async with get_sessionmaker()() as session:
        yield session

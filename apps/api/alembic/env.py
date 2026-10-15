"""Alembic environment (async, hybrid mode).

Reads the database URL from application config (never from alembic.ini), binds
``target_metadata`` to the ORM models for autogenerate drafts, and runs
migrations through the async psycopg 3 engine.

Autogenerate is a *draft helper only*: Postgres-specific objects (pgvector
columns, HNSW/GIN/pg_trgm indexes, CHECK constraints, triggers, RLS policies)
are hand-written in ``op.execute(...)``. See docs/DECISIONS.md.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import elenchus.db.models  # noqa: F401  (side-effect: register tables on Base.metadata)
from elenchus.config import get_settings
from elenchus.db.base import Base
from elenchus.db.session import normalise_async_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return normalise_async_url(get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url(), future=True)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

"""Schema drift test: ORM models must match the migrated database.

Integration test — runs only when ``TEST_DATABASE_URL`` points at a database
that has had ``alembic upgrade head`` applied (never production). It reflects the
real columns and asserts they match the SQLAlchemy models column-for-column, so
the migration (source of truth) and ``db/models.py`` can't silently diverge
(AGENTS.md section 12.4 / BUILD_PROMPTS Phase 1).

Without ``TEST_DATABASE_URL`` the test skips, so CI stays free of live calls.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from elenchus.db.base import Base
from elenchus.db.models import USER_OWNED_TABLES  # noqa: F401  (import keeps models registered)
from elenchus.db.session import normalise_async_url

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL (migrated, non-production) to run the schema drift test.",
)


def _db_columns(connection: Connection) -> dict[str, set[str]]:
    inspector = inspect(connection)
    return {
        table: {col["name"] for col in inspector.get_columns(table)}
        for table in Base.metadata.tables
    }


async def test_models_match_database() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(normalise_async_url(TEST_DATABASE_URL))
    try:
        async with engine.connect() as conn:
            db_columns = await conn.run_sync(_db_columns)
    finally:
        await engine.dispose()

    mismatches: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        model_cols = {c.name for c in table.columns}
        actual_cols = db_columns.get(table_name)
        if actual_cols is None:
            mismatches.append(f"{table_name}: missing from database")
            continue
        missing_in_db = model_cols - actual_cols
        extra_in_db = actual_cols - model_cols
        if missing_in_db:
            mismatches.append(f"{table_name}: in model but not DB: {sorted(missing_in_db)}")
        if extra_in_db:
            mismatches.append(f"{table_name}: in DB but not model: {sorted(extra_in_db)}")

    assert not mismatches, "Schema drift detected:\n" + "\n".join(mismatches)

"""Repository layer — the only place that builds SQL against the ORM models.

Phase 1 needs the fact-check corpus repository (idempotent upsert + stats).
More repositories are added per phase as features need them.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from elenchus.db.models import FactCheck
from elenchus.ingest.schemas import FactCheckRecord

# Columns refreshed when a fact-check already exists (keyed by review_url +
# claim_hash). Keys and claim_text are never updated.
_FACTCHECK_UPDATE_COLS = (
    "claim_language",
    "claimant",
    "claim_date",
    "publisher_name",
    "publisher_site",
    "review_title",
    "rating_text",
    "review_date",
    "image_url",
    "source",
    "raw_jsonld",
)


class UpsertResult(BaseModel):
    inserted: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated


class CorpusStats(BaseModel):
    total: int
    by_language: dict[str, int]
    by_publisher: dict[str, int]
    by_month: dict[str, int]


class FactCheckRepository:
    """Reads/writes for the global fact-check corpus."""

    @staticmethod
    async def upsert_many(
        session: AsyncSession, records: Sequence[FactCheckRecord]
    ) -> UpsertResult:
        """Idempotent bulk upsert on (review_url, claim_hash).

        Re-running ingestion over the same data inserts nothing new; it only
        refreshes mutable metadata. Insert-vs-update is counted via Postgres's
        ``xmax = 0`` idiom in the RETURNING clause.
        """
        if not records:
            return UpsertResult()

        # Deduplicate within the batch (keep last): Postgres rejects an
        # ON CONFLICT DO UPDATE that would touch the same row twice.
        by_key: dict[tuple[str, str], dict] = {}
        for record in records:
            row = record.to_row()
            by_key[(row["review_url"], row["claim_hash"])] = row
        rows = list(by_key.values())

        stmt = pg_insert(FactCheck).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["review_url", "claim_hash"],
            set_={col: getattr(stmt.excluded, col) for col in _FACTCHECK_UPDATE_COLS},
        )
        # Postgres system column trick: for each affected row, xmax = 0 means a
        # fresh INSERT, non-zero means the ON CONFLICT path updated an existing row.
        returning_stmt = stmt.returning(sa_text("(xmax = 0) AS inserted"))

        result = await session.execute(returning_stmt)
        flags = [bool(row[0]) for row in result.all()]
        inserted = sum(1 for f in flags if f)
        return UpsertResult(inserted=inserted, updated=len(flags) - inserted)

    @staticmethod
    async def count(session: AsyncSession) -> int:
        return int(
            (await session.execute(select(func.count()).select_from(FactCheck))).scalar_one()
        )

    @staticmethod
    async def stats(session: AsyncSession) -> CorpusStats:
        total = await FactCheckRepository.count(session)

        by_language = {
            (lang or "unknown"): n
            for lang, n in (
                await session.execute(
                    select(FactCheck.claim_language, func.count()).group_by(
                        FactCheck.claim_language
                    )
                )
            ).all()
        }
        by_publisher = {
            (pub or "unknown"): n
            for pub, n in (
                await session.execute(
                    select(FactCheck.publisher_name, func.count())
                    .group_by(FactCheck.publisher_name)
                    .order_by(func.count().desc())
                )
            ).all()
        }
        month = func.to_char(FactCheck.review_date, "YYYY-MM")
        by_month = {
            (m or "unknown"): n
            for m, n in (
                await session.execute(select(month, func.count()).group_by(month).order_by(month))
            ).all()
        }
        return CorpusStats(
            total=total,
            by_language=by_language,
            by_publisher=by_publisher,
            by_month=by_month,
        )

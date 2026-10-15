"""SQLAlchemy 2.0 ORM models mirroring the schema in AGENTS.md section 5.

These models describe the schema for the app to query. The **migrations** under
``alembic/versions/`` remain the source of truth for the actual DDL (extensions,
HNSW/GIN/pg_trgm indexes, CHECK constraints, triggers, RLS). A drift test
(``tests/test_schema_drift.py``) asserts the two agree on columns.

Conventions:
- UUID primary keys default to ``gen_random_uuid()`` (pgcrypto/pg built-in).
- ``created_at`` / ``updated_at`` default to ``now()``; ``updated_at`` is kept
  current by a trigger created in the migration.
- ``user_id`` is a bare UUID (no hard FK to Supabase's ``auth.users``); the
  backend always filters by it and RLS is the second layer (section 5, 8.3).
- Enums are modelled as plain strings; their allowed values are enforced by
  CHECK constraints in the migration.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from elenchus.config import get_settings
from elenchus.db.base import Base

# Vector dimension for the default (Gemini) embedding backend. The embeddings
# column is created with this fixed dimension; switching to bge-m3 (1024) is a
# self-hosting path that requires a migration + re-index (see docs/DECISIONS.md).
EMBEDDING_DIM = get_settings().embedding_dim


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# Users, sessions, usage
# --------------------------------------------------------------------------- #
class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    preferred_language: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=sa_text("'en'")
    )  # en | hi | mr
    report_style: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa_text("'brief'")
    )  # brief | detailed
    default_preset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_presets.id", ondelete="SET NULL")
    )
    strict_sources_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("true")
    )


class AnonSession(Base):
    __tablename__ = "anon_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()")
    )
    checks_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))


class Usage(UUIDPKMixin, Base):
    __tablename__ = "usage"
    __table_args__ = (UniqueConstraint("user_id", "anon_session_id", "date"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    anon_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("anon_sessions.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    checks_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))


# --------------------------------------------------------------------------- #
# Fact-check corpus (global) + embeddings
# --------------------------------------------------------------------------- #
class FactCheck(UUIDPKMixin, Base):
    __tablename__ = "factchecks"
    __table_args__ = (UniqueConstraint("review_url", "claim_hash"),)

    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_language: Mapped[str | None] = mapped_column(String(8))
    claimant: Mapped[str | None] = mapped_column(Text)
    claim_date: Mapped[date | None] = mapped_column(Date)
    publisher_name: Mapped[str | None] = mapped_column(Text)
    publisher_site: Mapped[str | None] = mapped_column(Text)
    review_url: Mapped[str] = mapped_column(Text, nullable=False)
    review_title: Mapped[str | None] = mapped_column(Text)
    rating_text: Mapped[str | None] = mapped_column(Text)
    review_date: Mapped[date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # gfc_api | claimreview_crawl
    raw_jsonld: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Embedding(UUIDPKMixin, Base):
    __tablename__ = "embeddings"

    owner_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # factcheck | library_chunk | claim
    owner_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    text_variant: Mapped[str] = mapped_column(String(16), nullable=False)  # original | en
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# Checks, events, claims
# --------------------------------------------------------------------------- #
class Check(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "checks"

    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    anon_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("anon_sessions.id", ondelete="SET NULL")
    )
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)  # text | url | image | pdf
    input_ref: Mapped[str | None] = mapped_column(Text)
    input_text: Mapped[str | None] = mapped_column(Text)
    detected_language: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=sa_text("'extracting'")
    )  # extracting | awaiting_confirmation | running | done | failed
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("1"))
    parent_check_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("checks.id", ondelete="SET NULL")
    )
    langgraph_thread_id: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class CheckEvent(UUIDPKMixin, Base):
    __tablename__ = "check_events"
    __table_args__ = (UniqueConstraint("check_id", "seq"),)

    check_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Claim(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "claims"

    check_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("checks.id", ondelete="CASCADE"), nullable=False
    )
    text_original: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    claim_type: Mapped[str | None] = mapped_column(
        String(16)
    )  # factual | opinion | prediction | other
    entities: Mapped[dict | None] = mapped_column(JSONB)
    time_reference: Mapped[str | None] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("true"))
    status: Mapped[str | None] = mapped_column(String(32))  # evidence status
    confidence: Mapped[float | None] = mapped_column(Float)
    summary_original: Mapped[str | None] = mapped_column(Text)
    summary_en: Mapped[str | None] = mapped_column(Text)
    matched_factcheck_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("factchecks.id", ondelete="SET NULL")
    )


# --------------------------------------------------------------------------- #
# Sources + evidence
# --------------------------------------------------------------------------- #
class Source(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    snapshot_text: Mapped[str | None] = mapped_column(Text)  # stored privately
    lang: Mapped[str | None] = mapped_column(String(8))


class ClaimSource(UUIDPKMixin, Base):
    __tablename__ = "claim_sources"
    __table_args__ = (UniqueConstraint("claim_id", "source_id"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    stance: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # supports | contradicts | context
    relevance: Mapped[float | None] = mapped_column(Float)
    trust_weight_applied: Mapped[float | None] = mapped_column(Float)
    quotes: Mapped[dict | None] = mapped_column(JSONB)  # verified quote spans


# --------------------------------------------------------------------------- #
# Claim graph
# --------------------------------------------------------------------------- #
class GraphNode(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "graph_nodes"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    node_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # claim | source | factcheck | entity | document | check
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    label: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB)


class GraphEdge(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "graph_edges"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    from_node: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # supports | contradicts | context | same_claim | cites | mentions | similar_to | derived_from
    origin: Mapped[str] = mapped_column(String(16), nullable=False)  # llm | system | user
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa_text("'active'")
    )  # active | suggested | dismissed
    confidence: Mapped[float | None] = mapped_column(Float)


# --------------------------------------------------------------------------- #
# Sources configuration (presets + domain rules)
# --------------------------------------------------------------------------- #
class SourcePreset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "source_presets"

    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))  # null = system preset
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa_text("'allowlist'")
    )  # allowlist
    domains: Mapped[dict | None] = mapped_column(JSONB)  # with optional wildcard patterns


class DomainRule(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "domain_rules"
    __table_args__ = (UniqueConstraint("user_id", "domain"),)

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    rule: Mapped[str] = mapped_column(String(8), nullable=False)  # allow | block
    trust_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=sa_text("1.0")
    )  # 0.5–1.5


# --------------------------------------------------------------------------- #
# Library
# --------------------------------------------------------------------------- #
class LibraryItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "library_items"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # check | source | document | note
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    title: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class Collection(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "collections"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CollectionItem(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("library_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Document(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa_text("'pending'")
    )


class LibraryChunk(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "library_chunks"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


# --------------------------------------------------------------------------- #
# Memory, reports, feedback
# --------------------------------------------------------------------------- #
class Memory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # language | preset | report_style | topic | source_preference | other
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa_text("'pending'")
    )  # pending | active | rejected
    proposed_by: Mapped[str] = mapped_column(String(8), nullable=False)  # agent | user
    evidence: Mapped[str | None] = mapped_column(Text)  # why it was proposed
    langmem_key: Mapped[str | None] = mapped_column(Text)


class Report(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # check | collection
    source_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    markdown: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[dict | None] = mapped_column(JSONB)
    share_token: Mapped[str | None] = mapped_column(Text, unique=True)
    share_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("false")
    )
    pdf_path: Mapped[str | None] = mapped_column(Text)


class Feedback(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    target_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # match | source | edge | status | report
    target_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))


# Tables owned by a user, protected by Row Level Security (section 5, 8.3).
# ``usage`` and ``anon_sessions`` are keyed by anon session too; RLS specifics
# live in the migration.
USER_OWNED_TABLES = (
    "profiles",
    "checks",
    "claims",
    "claim_sources",
    "graph_nodes",
    "graph_edges",
    "source_presets",
    "domain_rules",
    "library_items",
    "collections",
    "collection_items",
    "documents",
    "library_chunks",
    "memories",
    "reports",
    "feedback",
)

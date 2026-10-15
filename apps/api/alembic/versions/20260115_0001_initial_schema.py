"""initial schema (AGENTS.md section 5)

Creates the full V1 schema: extensions, all core tables, indexes
(HNSW / GIN full-text with the 'simple' config / pg_trgm), constraints,
updated_at triggers, and Row Level Security on user-owned tables.

Hand-authored SQL (hybrid Alembic mode) — autogenerate cannot express pgvector,
HNSW/GIN indexes, CHECK constraints, triggers or RLS. See docs/DECISIONS.md.

Revision ID: 0001
Revises:
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Vector dimension for the default Gemini embedding backend (EMBEDDING_DIM=1536).
# Switching to bge-m3 (1024) is a self-hosting path requiring a new migration and
# a full re-index (docs/DECISIONS.md).
EMBEDDING_DIM = 1536

# Tables with an updated_at column kept current by the trigger below.
_UPDATED_AT_TABLES = (
    "profiles",
    "checks",
    "claims",
    "sources",
    "graph_nodes",
    "graph_edges",
    "source_presets",
    "domain_rules",
    "library_items",
    "collections",
    "documents",
    "library_chunks",
    "memories",
    "reports",
    "feedback",
)

# Tables with Row Level Security enabled (owner-only). The backend connects with
# the service role (which bypasses RLS) and always filters by user_id; RLS is the
# second layer (AGENTS.md section 5, 8.3).
_RLS_DIRECT = (
    "profiles",
    "checks",
    "graph_nodes",
    "graph_edges",
    "domain_rules",
    "library_items",
    "collections",
    "documents",
    "library_chunks",
    "memories",
    "reports",
    "feedback",
)


def upgrade() -> None:
    # --- Extensions ---------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # --- Tables (dependency order) -----------------------------------------
    op.execute(
        """
        CREATE TABLE anon_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            checks_used integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            claimed_by_user_id uuid
        );
        """
    )

    op.execute(
        """
        CREATE TABLE source_presets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid,
            name text NOT NULL,
            description text,
            mode varchar(16) NOT NULL DEFAULT 'allowlist',
            domains jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_source_presets_mode CHECK (mode IN ('allowlist'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE profiles (
            user_id uuid PRIMARY KEY,
            display_name text,
            preferred_language varchar(8) NOT NULL DEFAULT 'en',
            report_style varchar(16) NOT NULL DEFAULT 'brief',
            default_preset_id uuid REFERENCES source_presets(id) ON DELETE SET NULL,
            strict_sources_default boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_profiles_preferred_language CHECK (preferred_language IN ('en','hi','mr')),
            CONSTRAINT ck_profiles_report_style CHECK (report_style IN ('brief','detailed'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE factchecks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            claim_text text NOT NULL,
            claim_hash varchar(64) NOT NULL,
            claim_language varchar(8),
            claimant text,
            claim_date date,
            publisher_name text,
            publisher_site text,
            review_url text NOT NULL,
            review_title text,
            rating_text text,
            review_date date,
            image_url text,
            source varchar(32) NOT NULL,
            raw_jsonld jsonb,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_factchecks_review_url_claim_hash UNIQUE (review_url, claim_hash),
            CONSTRAINT ck_factchecks_source CHECK (source IN ('gfc_api','claimreview_crawl'))
        );
        """
    )

    op.execute(
        f"""
        CREATE TABLE embeddings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_type varchar(16) NOT NULL,
            owner_id uuid NOT NULL,
            model text NOT NULL,
            dim integer NOT NULL,
            vector vector({EMBEDDING_DIM}) NOT NULL,
            text_variant varchar(16) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_embeddings_owner_type
                CHECK (owner_type IN ('factcheck','library_chunk','claim')),
            CONSTRAINT ck_embeddings_text_variant CHECK (text_variant IN ('original','en'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid,
            anon_session_id uuid REFERENCES anon_sessions(id) ON DELETE SET NULL,
            input_type varchar(16) NOT NULL,
            input_ref text,
            input_text text,
            detected_language varchar(8),
            status varchar(32) NOT NULL DEFAULT 'extracting',
            version integer NOT NULL DEFAULT 1,
            parent_check_id uuid REFERENCES checks(id) ON DELETE SET NULL,
            langgraph_thread_id text,
            cost_usd double precision,
            duration_ms integer,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_checks_input_type CHECK (input_type IN ('text','url','image','pdf')),
            CONSTRAINT ck_checks_status CHECK (
                status IN ('extracting','awaiting_confirmation','running','done','failed')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE check_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            check_id uuid NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
            seq integer NOT NULL,
            type varchar(32) NOT NULL,
            payload jsonb,
            ts timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_check_events_check_id_seq UNIQUE (check_id, seq)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE claims (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            check_id uuid NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
            text_original text NOT NULL,
            text_en text,
            language varchar(8),
            claim_type varchar(16),
            entities jsonb,
            time_reference text,
            selected boolean NOT NULL DEFAULT true,
            status varchar(32),
            confidence double precision,
            summary_original text,
            summary_en text,
            matched_factcheck_id uuid REFERENCES factchecks(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_claims_claim_type CHECK (
                claim_type IS NULL OR claim_type IN ('factual','opinion','prediction','other')
            ),
            CONSTRAINT ck_claims_status CHECK (
                status IS NULL OR status IN (
                    'ALREADY_FACT_CHECKED','EVIDENCE_FOUND','INSUFFICIENT_EVIDENCE'
                )
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE sources (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            url text NOT NULL,
            domain text,
            title text,
            publisher text,
            published_at timestamptz,
            fetched_at timestamptz,
            content_hash varchar(64),
            snapshot_text text,
            lang varchar(8),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sources_url UNIQUE (url)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE claim_sources (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            stance varchar(16) NOT NULL,
            relevance double precision,
            trust_weight_applied double precision,
            quotes jsonb,
            CONSTRAINT uq_claim_sources_claim_id_source_id UNIQUE (claim_id, source_id),
            CONSTRAINT ck_claim_sources_stance CHECK (
                stance IN ('supports','contradicts','context')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE graph_nodes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            node_type varchar(16) NOT NULL,
            ref_id uuid,
            label text,
            meta jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_graph_nodes_node_type CHECK (
                node_type IN ('claim','source','factcheck','entity','document','check')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE graph_edges (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            from_node uuid NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
            to_node uuid NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
            edge_type varchar(24) NOT NULL,
            origin varchar(16) NOT NULL,
            state varchar(16) NOT NULL DEFAULT 'active',
            confidence double precision,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_graph_edges_edge_type CHECK (
                edge_type IN (
                    'supports','contradicts','context','same_claim','cites',
                    'mentions','similar_to','derived_from'
                )
            ),
            CONSTRAINT ck_graph_edges_origin CHECK (origin IN ('llm','system','user')),
            CONSTRAINT ck_graph_edges_state CHECK (state IN ('active','suggested','dismissed'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE domain_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            domain text NOT NULL,
            rule varchar(8) NOT NULL,
            trust_weight double precision NOT NULL DEFAULT 1.0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_domain_rules_user_id_domain UNIQUE (user_id, domain),
            CONSTRAINT ck_domain_rules_rule CHECK (rule IN ('allow','block')),
            CONSTRAINT ck_domain_rules_trust_weight CHECK (trust_weight BETWEEN 0.5 AND 1.5)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE library_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            item_type varchar(16) NOT NULL,
            ref_id uuid,
            title text,
            notes text,
            tags text[],
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_library_items_item_type CHECK (
                item_type IN ('check','source','document','note')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE collections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            name text NOT NULL,
            description text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE collection_items (
            collection_id uuid NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            library_item_id uuid NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_collection_items PRIMARY KEY (collection_id, library_item_id)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            storage_path text NOT NULL,
            mime text,
            pages integer,
            text text,
            language varchar(8),
            status varchar(16) NOT NULL DEFAULT 'pending',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_documents_status CHECK (
                status IN ('pending','processing','done','failed')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE library_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            document_id uuid REFERENCES documents(id) ON DELETE CASCADE,
            source_id uuid REFERENCES sources(id) ON DELETE CASCADE,
            chunk_index integer NOT NULL,
            text text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE memories (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            kind varchar(24) NOT NULL,
            content text NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'pending',
            proposed_by varchar(8) NOT NULL,
            evidence text,
            langmem_key text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_memories_kind CHECK (
                kind IN ('language','preset','report_style','topic','source_preference','other')
            ),
            CONSTRAINT ck_memories_status CHECK (status IN ('pending','active','rejected')),
            CONSTRAINT ck_memories_proposed_by CHECK (proposed_by IN ('agent','user'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE reports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            source_type varchar(16) NOT NULL,
            source_id uuid NOT NULL,
            title text,
            markdown text,
            structured jsonb,
            share_token text,
            share_enabled boolean NOT NULL DEFAULT false,
            pdf_path text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_reports_share_token UNIQUE (share_token),
            CONSTRAINT ck_reports_source_type CHECK (source_type IN ('check','collection'))
        );
        """
    )

    op.execute(
        """
        CREATE TABLE feedback (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid,
            target_type varchar(16) NOT NULL,
            target_id uuid,
            kind text,
            comment text,
            resolved boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_feedback_target_type CHECK (
                target_type IN ('match','source','edge','status','report')
            )
        );
        """
    )

    op.execute(
        """
        CREATE TABLE usage (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid,
            anon_session_id uuid REFERENCES anon_sessions(id) ON DELETE CASCADE,
            date date NOT NULL,
            checks_count integer NOT NULL DEFAULT 0,
            CONSTRAINT uq_usage_user_id_anon_session_id_date UNIQUE (user_id, anon_session_id, date)
        );
        """
    )

    # --- Indexes ------------------------------------------------------------
    # Fact-check retrieval (Phase 2): keyword (simple FTS) + trigram + metadata.
    op.execute(
        "CREATE INDEX ix_factchecks_claim_text_fts ON factchecks "
        "USING gin (to_tsvector('simple', claim_text));"
    )
    op.execute(
        "CREATE INDEX ix_factchecks_claim_text_trgm ON factchecks "
        "USING gin (claim_text gin_trgm_ops);"
    )
    op.execute("CREATE INDEX ix_factchecks_publisher_site ON factchecks (publisher_site);")
    op.execute("CREATE INDEX ix_factchecks_claim_language ON factchecks (claim_language);")
    op.execute("CREATE INDEX ix_factchecks_review_date ON factchecks (review_date);")

    # Embeddings: HNSW (cosine) for dense retrieval, plus lookup indexes. A single
    # HNSW index suffices for the V1 single-model setup; multiple models would use
    # per-model partial indexes ("never mix models in one index").
    op.execute(
        "CREATE INDEX ix_embeddings_vector_hnsw ON embeddings "
        "USING hnsw (vector vector_cosine_ops);"
    )
    op.execute("CREATE INDEX ix_embeddings_owner ON embeddings (owner_type, owner_id);")
    op.execute("CREATE INDEX ix_embeddings_model ON embeddings (model);")

    # Foreign-key / filter indexes.
    op.execute("CREATE INDEX ix_checks_user_id ON checks (user_id);")
    op.execute("CREATE INDEX ix_checks_anon_session_id ON checks (anon_session_id);")
    op.execute("CREATE INDEX ix_checks_status ON checks (status);")
    op.execute("CREATE INDEX ix_claims_check_id ON claims (check_id);")
    op.execute("CREATE INDEX ix_claims_matched_factcheck_id ON claims (matched_factcheck_id);")
    op.execute("CREATE INDEX ix_claim_sources_source_id ON claim_sources (source_id);")
    op.execute("CREATE INDEX ix_sources_domain ON sources (domain);")
    op.execute("CREATE INDEX ix_graph_nodes_user_id ON graph_nodes (user_id);")
    op.execute("CREATE INDEX ix_graph_edges_user_id ON graph_edges (user_id);")
    op.execute("CREATE INDEX ix_graph_edges_from_node ON graph_edges (from_node);")
    op.execute("CREATE INDEX ix_graph_edges_to_node ON graph_edges (to_node);")
    op.execute("CREATE INDEX ix_library_items_user_id ON library_items (user_id);")
    op.execute("CREATE INDEX ix_library_items_tags ON library_items USING gin (tags);")
    op.execute("CREATE INDEX ix_collections_user_id ON collections (user_id);")
    op.execute("CREATE INDEX ix_documents_user_id ON documents (user_id);")
    op.execute("CREATE INDEX ix_library_chunks_user_id ON library_chunks (user_id);")
    op.execute("CREATE INDEX ix_memories_user_id ON memories (user_id);")
    op.execute("CREATE INDEX ix_reports_user_id ON reports (user_id);")
    op.execute("CREATE INDEX ix_feedback_user_id ON feedback (user_id);")

    # --- updated_at trigger -------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in _UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )

    # --- Row Level Security -------------------------------------------------
    # Direct-owner tables: a row is visible/writable only to its owner. Supabase's
    # auth.uid() returns the authenticated user id. source_presets additionally
    # exposes system presets (user_id IS NULL) read-only.
    for table in _RLS_DIRECT:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY {table}_owner ON {table} "
            f"USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());"
        )

    op.execute("ALTER TABLE source_presets ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY source_presets_read ON source_presets FOR SELECT "
        "USING (user_id IS NULL OR user_id = auth.uid());"
    )
    op.execute(
        "CREATE POLICY source_presets_write ON source_presets FOR ALL "
        "USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());"
    )

    # Child tables inherit ownership through their parent.
    op.execute("ALTER TABLE claims ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY claims_owner ON claims USING (EXISTS ("
        "SELECT 1 FROM checks c WHERE c.id = claims.check_id AND c.user_id = auth.uid()));"
    )
    op.execute("ALTER TABLE claim_sources ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY claim_sources_owner ON claim_sources USING (EXISTS ("
        "SELECT 1 FROM claims cl JOIN checks c ON c.id = cl.check_id "
        "WHERE cl.id = claim_sources.claim_id AND c.user_id = auth.uid()));"
    )
    op.execute("ALTER TABLE collection_items ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY collection_items_owner ON collection_items USING (EXISTS ("
        "SELECT 1 FROM collections col WHERE col.id = collection_items.collection_id "
        "AND col.user_id = auth.uid()));"
    )


def downgrade() -> None:
    tables = [
        "usage",
        "feedback",
        "reports",
        "memories",
        "library_chunks",
        "documents",
        "collection_items",
        "collections",
        "library_items",
        "domain_rules",
        "graph_edges",
        "graph_nodes",
        "claim_sources",
        "sources",
        "claims",
        "check_events",
        "checks",
        "embeddings",
        "factchecks",
        "profiles",
        "source_presets",
        "anon_sessions",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

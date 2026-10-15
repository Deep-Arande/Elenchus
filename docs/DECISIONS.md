# Decisions log

Every deviation from the spec or non-obvious choice, dated and with a reason
(AGENTS.md section 12.3). Newest first.

---

## 2026-10-15 — Migrations: Alembic (hybrid) instead of Supabase-CLI SQL files

**Decision.** Schema migrations are hand-authored **Alembic** revisions under
`apps/api/alembic/versions/`, not `.sql` files applied via the Supabase CLI.
AGENTS.md section 3 (and the section 4 tree) were updated to match. Also added
the `pgvector` Python package — the standard SQLAlchemy/psycopg adapter for the
already-specced pgvector extension, needed to map vector columns in the ORM.

**Why.** We access Supabase **cloud directly via `DATABASE_URL`** (keys), not a
local Supabase stack. The Supabase CLI needs Docker, which isn't part of this
workflow; Alembic is a pure-Python runner that applies migrations against any
`DATABASE_URL` (`alembic upgrade head`) with a proper version chain and
up/down revisions.

**How (hybrid).** Autogenerate is a draft helper only. Every Postgres-specific
object — `CREATE EXTENSION`, pgvector columns, HNSW / GIN-`simple`-FTS /
`pg_trgm` indexes, CHECK constraints, the `updated_at` trigger, and RLS
policies — is hand-written in `op.execute(...)`. `env.py` reads the URL from
`elenchus.config` (no secret in `alembic.ini`) and runs through the async
psycopg 3 engine.

**Consequences.**
- The migration is the schema source of truth; `db/models.py` mirrors it and a
  drift test (`tests/test_schema_drift.py`) asserts they agree on columns.
- Version tracking lives in Alembic's `alembic_version` table, not Supabase's
  `supabase_migrations`. Applying still needs the cloud `DATABASE_URL`.
- `supabase/migrations/` is removed; `supabase/seed.sql` stays for seed data.

---

## 2026-10-15 — Retrieval defaults: Gemini embeddings + LLM reranker

**Decision.** The V1 default `EMBEDDING_BACKEND` is `gemini` (not `bge-m3`) and
the default `RERANKER_BACKEND` is `llm` (not `local`). AGENTS.md section 3 was
updated to match.

**Why.** The two local models (`BAAI/bge-m3`, ~1024-dim, and
`BAAI/bge-reranker-v2-m3`) each need a multi-GB resident process. That does not
fit the small hosted instances named for api/worker (Render/Railway) and would
force a larger paid tier or OOM on boot. Gemini embeddings/reranking move that
cost off the box and onto per-call API usage, which counts against
`CHECK_MAX_COST_USD`.

**Consequences.**
- Develop and tune on the backend we deploy. Switching backends later forces a
  full corpus re-index (vectors are not interchangeable across models) and may
  shift `MATCH_THRESHOLD` and eval numbers.
- Before the Phase 2 `embed reindex`, set `GEMINI_EMBEDDING_MODEL` and
  `EMBEDDING_DIM` — the whole corpus is embedded into that one vector space.
- The `bge-m3` / `local` options remain available for self-hosting on adequate
  hardware, and the section 11 embedding ablation still measures the trade-off.

---

## 2026-10-15 — Phase 0 tooling notes

- **uv** installed via `pip install --user uv`; it provisions Python 3.12 itself
  (the host had 3.14/3.10 only).
- **Tailwind v3.4** chosen over v4 for Phase 0 to keep the Phase 5 token mapping
  and shadcn/ui setup on the well-trodden config path. Revisit if needed.
- **ESLint 8.57 + `.eslintrc.json`** (`next/core-web-vitals`) rather than flat
  config, for the least-friction `next lint` setup.
- Frontend scaffolded by hand (not `create-next-app`) for a deterministic,
  reviewable Phase 0 tree.

# Progress

Phase checklist and, per phase, what was built, how to test it manually and
known issues (AGENTS.md section 15).

## Phase checklist

- [x] **Phase 0** — Scaffold, tooling, CI
- [ ] **Phase 1** — Database schema + fact-check corpus ingestion
- [ ] **Phase 2** — Retrieval, claim matching, benchmark + eval harness
- [ ] **Phase 3** — Input processing + claim extraction
- [ ] **Phase 4** — Search providers + evidence agent (LangGraph) + streaming
- [ ] **Phase 5** — Auth, app shell, design system, check pages, home, landing
- [ ] **Phase 6** — Library: save, collections, tags, uploads, search, re-run
- [ ] **Phase 7** — Claim graph + timeline + cross-check linking
- [ ] **Phase 8** — Sources page, memory, settings, reports
- [ ] **Phase 9** — Polish, quotas, evals report, About page, deploy, case study

---

## Phase 0 — Scaffold, tooling, CI

**Status:** done.

### What was built
- Monorepo structure from AGENTS.md section 4 (placeholder packages with
  docstrings for db, llm, inputs, ingest, retrieval, search, agent, claimgraph,
  memory, library, reports; evals tree; supabase tree).
- **Backend (`apps/api`)** — uv project pinned to Python 3.12; FastAPI app
  factory (`create_app`) with `GET /health` returning `status`, `version` and
  `git_sha`; `config.py` loading every variable in AGENTS.md section 14 with
  documented defaults (retrieval defaults are Gemini embeddings + LLM reranker);
  ruff + mypy (strict on `agent/`, `retrieval/`, `search/`) + pytest configured.
- **Worker** — arq `WorkerSettings` with a sample no-op job and a sample no-op
  daily cron, both tested.
- **Langfuse** — minimal wrapper that no-ops when keys (or the package) are
  absent, so dev/CI need no credentials.
- **Frontend (`apps/web`)** — Next.js App Router + TypeScript strict + Tailwind
  v3 + shadcn/ui setup (`components.json`, `cn` util) + next-intl with
  `en`/`hi`/`mr` message files; placeholder home page rendering localized copy
  and the research-demo disclaimer.
- **API types** — `uv run elenchus-export-openapi` writes `apps/api/openapi.json`;
  `pnpm gen:api-types` turns it into `apps/web/lib/api-types.ts` (committed).
- **Infra** — `.env.example` (exactly AGENTS.md section 14, Gemini-embedding
  defaults); `docker-compose.yml` for api, worker, redis, web; Dockerfiles for
  api and web; Supabase run via the Supabase CLI (see README).
- **CI** — `.github/workflows/ci.yml`: api job (ruff, ruff format, mypy, pytest);
  web job (eslint, tsc). No external API calls.
- **Docs** — this file, `DECISIONS.md`, `ARCHITECTURE.md` (Mermaid), `README.md`.

### How to test manually
Backend (from `apps/api`):
```
uv sync --python 3.12
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
uv run uvicorn elenchus.main:app --reload   # then open http://localhost:8000/health
```
Frontend (from `apps/web`):
```
pnpm install
pnpm lint && pnpm tsc
pnpm dev                                     # then open http://localhost:3000
```
Regenerate API types (from `apps/api` then `apps/web`):
```
uv run elenchus-export-openapi openapi.json
cd ../web && pnpm gen:api-types
```
Full stack (needs Docker + Supabase CLI):
```
supabase start
docker compose up --build
# http://localhost:8000/health and http://localhost:3000 both respond
```

### Verified here
- `uv run ruff check .` — pass; `ruff format --check` — 32 files formatted.
- `uv run mypy src` — pass (26 files).
- `uv run pytest` — 7 passed (health + worker + config defaults).
- `pnpm tsc` — pass; `pnpm lint` — no warnings/errors.
- OpenAPI export + `pnpm gen:api-types` — generated `lib/api-types.ts`.

### Known issues / not verified here
- **Docker & Supabase not available in this build environment**, so
  `docker compose up --build` and `supabase start` were not executed. The
  Dockerfiles and compose file are written to spec but unverified; confirm on a
  machine with Docker before relying on them.
- Host had Python 3.14/3.10 only; uv provisions 3.12 for the project.
- `GEMINI_EMBEDDING_MODEL` / `EMBEDDING_DIM` must be set before Phase 2
  indexing (see DECISIONS.md).

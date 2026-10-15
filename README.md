# Elenchus

**A personal fact-checking workspace for Indian users (English, Hindi, Marathi).**
Elenchus surfaces *evidence* — it never gives a "true" or "fake" verdict. Paste
text, a link, a screenshot or a PDF; it extracts the checkable claims, matches
them against published fact-checks, and when nothing matches runs a bounded,
observable evidence agent over the sources you trust.

> Elenchus is a research demo. It surfaces evidence; it does not give verdicts.
> Always read the sources.

"Elenchus" (ἔλεγχος) is Socrates' method of testing a claim by cross-examination.

This README is the setup guide; it becomes the full portfolio case study in the
final phase. See [`AGENTS.md`](AGENTS.md) for the governing spec and
[`BUILD_PROMPTS.md`](BUILD_PROMPTS.md) for the phase-by-phase build plan.

---

## Repository layout

```
apps/api/    FastAPI backend + arq worker (Python 3.12, uv)
apps/web/    Next.js frontend (TypeScript, Tailwind, next-intl)
supabase/    SQL migrations + seed (schema source of truth)
docs/        DECISIONS.md, PROGRESS.md, ARCHITECTURE.md
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (provisions Python 3.12 itself)
- Node 20+ and [pnpm](https://pnpm.io/) 10+
- Docker (for the full local stack)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (local Postgres)
- API keys for later phases: Gemini, Firecrawl, Google Fact Check Tools,
  Supabase project, Langfuse (optional). Brave/Exa are optional.

## Setup

```bash
cp .env.example .env    # fill in keys as phases need them
```

### Backend (`apps/api`)

```bash
cd apps/api
uv sync --python 3.12
uv run uvicorn elenchus.main:app --reload   # http://localhost:8000/health
```

Checks (what CI runs):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
```

Run the worker:

```bash
uv run arq elenchus.jobs.worker.WorkerSettings
```

### Frontend (`apps/web`)

```bash
cd apps/web
pnpm install
pnpm dev                                     # http://localhost:3000
pnpm lint && pnpm tsc
```

### Generate API types

The frontend's API types are generated from the backend's OpenAPI schema:

```bash
cd apps/api && uv run elenchus-export-openapi openapi.json
cd ../web && pnpm gen:api-types              # -> lib/api-types.ts
```

### Full local stack (Docker + Supabase)

```bash
supabase start          # local Postgres (pgvector/pg_trgm), prints a DATABASE_URL
docker compose up --build   # api, worker, redis, web
```

`docker compose` runs api/worker/redis/web; Supabase runs separately via its CLI
and is reached from the containers at `host.docker.internal`.

## Core principles

- **Evidence, not verdicts.** Three per-claim statuses: `ALREADY_FACT_CHECKED`,
  `EVIDENCE_FOUND`, `INSUFFICIENT_EVIDENCE`.
- **Every statement is backed by a verified citation.**
- **Untrusted content is data, never instructions.**
- **Memory changes presentation, never the standard of evidence.**

See [`docs/PROGRESS.md`](docs/PROGRESS.md) for current status and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for diagrams.

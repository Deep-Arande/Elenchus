# Elenchus — Quick Prototype Plan & Full-Project Roadmap

> **Status:** planning. This document describes a fast, throwaway prototype we
> build first to prove the experience end-to-end, and the serious full project
> (governed by [`AGENTS.md`](../AGENTS.md)) we build properly afterwards.
> As of 2026-10-15. No prototype code has been written yet.

---

## 1. What the quick prototype is

A **vertical slice**: one thin path through the whole product, built as fast as
possible so we can see and feel the real experience before investing in the
full architecture. It is **throwaway UX-first scaffolding**, not the foundation
of the real system.

**The single path a user walks:**

1. Paste text (e.g. a WhatsApp forward) into a box.
2. The app **extracts the checkable claims** and shows them; the user can
   untick ones they don't care about.
3. The user hits **Check**.
4. A **live trace** streams on screen: queries run, sources found, pages read.
5. Each claim gets a **result card**: an evidence **status**, a short cited
   summary, and the evidence (quotes + source links).
6. The claims and their sources are drawn as an **interactive graph**.
7. The user can switch **output language**, remembered **for this session only**
   (never saved).

The point is to answer "does this feel right?" quickly — not to be correct,
complete, or durable.

### Prototype architecture decisions (chosen for speed)

- **Fully in-memory** — no database. Checks, results and the graph live in
  backend memory and vanish on restart. (Supabase gets wired in for the real
  build.)
- **Text input only** — no URL / image / PDF yet.
- **Simple async pipeline** — plain `async` functions streaming over SSE, not
  the full LangGraph agent.
- **Mock fallback** — if API keys are absent, the flow runs on deterministic
  fake data so the frontend is fully demoable without keys.

---

## 2. What the prototype includes (and how, lightly)

| Feature | How it works in the prototype |
|---|---|
| Claim extraction | One Gemini call (structured output) turns pasted text into a short list of claims. |
| Search | Per claim, a query or two to Firecrawl; fetch the top 2–3 pages. |
| Evidence + result | Gemini reads the pages, pulls quotes with a stance (supports / contradicts / context), writes a 2–4 sentence cited summary, and assigns a status: **EVIDENCE_FOUND** or **INSUFFICIENT_EVIDENCE**. A light check confirms quotes exist in the fetched text. |
| Live trace | The pipeline emits events (query, sources, pages read, evidence, status, done) streamed to the UI over SSE. |
| Graph | Claims and their sources become nodes; edges show which source supports/contradicts/contextualises which claim. Rendered with Cytoscape. |
| Session memory | Output-language / preset preference held in memory keyed by an anonymous session; **not persisted**, lost when the session ends. |
| Frontend | Polished: light/dark, the editorial look from the spec, clean result cards and trace timeline. "The frontend should be good." |

---

## 3. Deliberately cut from the prototype (add back in the real build)

Each is skipped purely to move fast — not because it's unimportant:

- **Fact-check corpus matching** (the `ALREADY_FACT_CHECKED` status) — needs an
  ingested corpus + embeddings; heavy.
- **Persistence / Supabase** — prototype is in-memory.
- **Auth & anonymous quotas** — no login.
- **Library, collections, uploads** — nothing is saved.
- **Reports (PDF / Markdown / share links)**.
- **Persistent, approval-based memory** — prototype memory is session-only.
- **Evaluation harness** (benchmark, metrics, red-team, memory-bias).
- **URL / image / PDF inputs**.
- **Redis / arq background workers** — pipeline runs in-process.
- **Full LangGraph** (Postgres checkpointer, confirmation interrupt).
- **Deployment / CI hardening** — run locally only.

---

## 4. The full project (the serious build)

Governed by [`AGENTS.md`](../AGENTS.md). The real Elenchus is a personal
fact-checking workspace for Indian users (English, Hindi, Marathi) built to
portfolio quality, where engineering, evaluation, safety and UX matter more
than feature count. Key pillars we implement properly:

- **Evidence, not verdicts** — three per-claim statuses, every statement backed
  by a verified citation, honest uncertainty, research-demo disclaimer.
- **Fact-check matching** over an ingested corpus of Indian + international
  fact-checks (Google Fact Check Tools API + ClaimReview crawl), using hybrid
  retrieval (pgvector dense + Postgres keyword + trigram → RRF → rerank → LLM
  same-claim judge).
- **Bounded evidence agent** in **LangGraph** (fan-out per claim, budgets,
  deterministic citation verification, graceful stops) streaming a glass-box
  trace.
- **Supabase Postgres** persistence with Row Level Security; schema via Alembic;
  SQLAlchemy 2.0 async.
- **Auth** (Supabase JWT) with anonymous free checks and daily quotas.
- **Library** — save checks/sources/documents, collections, tags, uploads, and
  private library evidence feeding future checks.
- **Claim graph + timeline** with cross-check linking and entity merging.
- **Approval-based memory** (LangMem) that changes presentation only — never
  the standard of evidence — with a pending → approved flow.
- **Reports** — cited, styled, exportable to PDF/Markdown with read-only share
  links.
- **Evaluation as a product feature** — ~300-query benchmark, metrics,
  ablations, red-team injection set, memory-bias test.
- **Observability** (Langfuse), **i18n** (en/hi/mr), and **deployment + CI**.

Retrieval defaults for the real build are **Gemini embeddings + LLM reranker**
(see [`DECISIONS.md`](./DECISIONS.md)); migrations run via **Alembic** against
hosted Supabase.

---

## 5. How the prototype graduates into the full project

The prototype is throwaway, but it de-risks the UX and the agent shape. Mapping:

| Prototype (now) | Full project (later) |
|---|---|
| In-memory store, no DB | Supabase + SQLAlchemy repositories + RLS |
| Simple async pipeline | Full LangGraph agent (budgets, interrupt, checkpointer) |
| No fact-check matching | Ingested corpus + hybrid retrieval + same-claim judge |
| Text input only | Text / URL / image (OCR) / PDF |
| Session-only language memory | Approval-based LangMem memory (presentation-only) |
| Mock fallback for missing keys | Real Gemini + Firecrawl only; mocks become test fixtures |
| No save | Library, collections, reports, sharing |
| Eyeball the output | Benchmark + metrics + red-team + memory-bias evals |
| Local, ephemeral | Deployed (web + api + worker + Redis + Supabase), CI green |

---

## 6. What's needed to run the prototype + current status

**To run with real results:**
- `GEMINI_API_KEY` — claim extraction + evidence/compose.
- `FIRECRAWL_API_KEY` — web search + page fetch.
- Without these, the prototype runs in **mock mode** (deterministic fake data)
  so the frontend still works end-to-end.
- **No database required** — nothing is persisted.

**Current repo status:**
- Phase 0 (scaffold, tooling, CI) — done.
- Phase 1 (DB schema + ingestion) — written, but **not used by the prototype**
  (the prototype is in-memory). It stays in the repo for the serious build.
- Prototype code — **not started; paused pending go-ahead.**

---

_This is a living plan. When the prototype proves the experience, we switch to
building the serious project phase by phase per `AGENTS.md` and
`BUILD_PROMPTS.md`._

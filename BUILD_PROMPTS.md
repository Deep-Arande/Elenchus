# BUILD_PROMPTS.md — Step-by-step implementation prompts for Elenchus V1

## How to use this file

1. Create an empty Git repo named `elenchus`. Put `AGENTS.md` and this file in the root and commit them.
2. Most AI code editors read `AGENTS.md` automatically. If yours doesn't, start each session with: *"Read AGENTS.md fully before doing anything."*
3. Run **one phase at a time**: paste the phase prompt, let the editor plan and build, then go through the **Done when** checklist yourself. Commit, then move to the next phase.
4. If a phase is too large for one session, say: *"Continue Phase N from where you stopped; check docs/PROGRESS.md first."*
5. Before starting, collect API keys: Gemini, Firecrawl, Google Fact Check Tools, Supabase project, Langfuse (cloud free tier is fine). Brave/Exa are optional.

| Phase | Focus | Rough time |
|---|---|---|
| 0 | Repo scaffold, tooling, CI | 1–2 days |
| 1 | Database schema + fact-check corpus ingestion | week 1 |
| 2 | Retrieval, claim matching, benchmark + eval harness | week 2 |
| 3 | Input processing + claim extraction | week 3 |
| 4 | Search providers + evidence agent (LangGraph) + streaming | week 4 |
| 5 | Auth, app shell, design system, New check + Check result pages, Home, Landing | week 5 |
| 6 | Library: save, collections, tags, uploads, search, re-run | week 6 |
| 7 | Claim graph + timeline + cross-check linking | week 7 |
| 8 | Sources page, Memory, Settings, Reports | week 8 |
| 9 | Polish, quotas, evals report, About page, deploy, README case study | week 9 |

---

## Phase 0 — Scaffold, tooling, CI

~~~text
Read AGENTS.md fully. Implement ONLY Phase 0.

Goal: an empty but fully wired monorepo that runs locally with one command and has CI.

Tasks:
1. Create the repository structure from AGENTS.md section 4 (empty modules with docstrings are fine).
2. Backend (apps/api): uv project, Python 3.12, FastAPI app factory with GET /health returning version and git sha; config.py with pydantic-settings loading every variable in AGENTS.md section 14 (with defaults where documented); ruff + mypy + pytest configured; a first test for /health.
3. Worker: arq worker entrypoint with one sample job and one sample cron job (no-op), both tested.
4. Frontend (apps/web): Next.js App Router + TypeScript strict + Tailwind + shadcn/ui initialised; next-intl set up with en.json/hi.json/mr.json; a placeholder home page; eslint + tsc scripts.
5. Local infra: docker-compose.yml for api, worker, redis, web; instructions to run Supabase locally with the Supabase CLI (supabase start); .env.example exactly as AGENTS.md section 14.
6. API types: script that exports FastAPI OpenAPI JSON and generates apps/web/lib/api-types.ts with openapi-typescript.
7. Langfuse: minimal client wrapper in the backend (no-op when keys are missing).
8. CI (.github/workflows/ci.yml): ruff, mypy, pytest (api); eslint, tsc (web). No external API calls.
9. Docs: docs/DECISIONS.md, docs/PROGRESS.md (phase checklist 0–9), docs/ARCHITECTURE.md (first diagram in Mermaid), README.md with setup steps.

Do not build any product features yet.

Done when:
- `docker compose up` + `supabase start` brings everything up; http://localhost:8000/health and http://localhost:3000 both respond.
- CI passes on a fresh push.
- docs/PROGRESS.md lists how to run and test Phase 0.
~~~

---

## Phase 1 — Database schema + fact-check corpus

~~~text
Read AGENTS.md (sections 5, 7.2, 8, 12). Implement ONLY Phase 1.

Goal: the full V1 schema exists, and a growing corpus of Indian and international fact-checks is ingested, deduplicated and refreshable.

Tasks:
1. Write SQL migrations in supabase/migrations for ALL tables in AGENTS.md section 5, including indexes: pgvector HNSW on embeddings (per model), GIN full-text index with the 'simple' configuration, pg_trgm GIN index on claim text, foreign keys, unique constraints, created_at/updated_at triggers. Enable Row Level Security on user-owned tables with owner-only policies.
2. SQLAlchemy 2.0 async models + repository layer mirroring the migrations (no schema drift: add a test that compares model columns to the database).
3. Google Fact Check Tools ingestion (ingest/factcheck_api.py): claims search with paging, by seed topic lists and by publisher site, language codes en/hi/mr; normalise into `factchecks`; idempotent upsert; retries with backoff; respect quota.
4. ClaimReview crawler (ingest/claimreview_crawler.py): read ingest/sources.yaml (Indian fact-checkers and a few international ones: name, homepage, rss_or_sitemap, language, enabled). Verify each feed works; set enabled=false for broken ones and log in docs/DECISIONS.md. Fetch article pages politely (robots.txt, delay, User-Agent), parse ClaimReview JSON-LD with extruct, store metadata only (never full article text).
5. CLI commands: `ingest factchecks --since <date>`, `ingest crawl`, `ingest stats` (counts by publisher, language, month).
6. arq cron job: daily incremental ingestion.
7. Tests: parsers with saved fixture JSON/HTML, dedup logic, upsert idempotency.

Target: at least 5,000 fact-checks with a healthy share of Hindi and Marathi where available. Report actual numbers in PROGRESS.md.

Done when:
- Migrations apply cleanly on a fresh local Supabase.
- `ingest stats` shows the corpus with counts by language and publisher.
- Running ingestion twice creates no duplicates.
~~~

---

## Phase 2 — Retrieval, claim matching, benchmark and eval harness

~~~text
Read AGENTS.md (sections 7.1, 11, 12). Implement ONLY Phase 2.

Goal: given a claim string, return the best matching fact-checks with a calibrated match decision, and measure it with a real benchmark.

Tasks:
1. retrieval/embeddings.py: EmbeddingBackend interface; BGE-M3 implementation (batching, CPU-friendly) and Gemini implementation; store vectors with model + dim; command `embed reindex --backend <name>` that embeds the whole corpus (original text and English translation).
2. retrieval/keyword.py: Postgres full-text ('simple') + pg_trgm queries.
3. retrieval/hybrid.py: dense + keyword + trigram candidates fused with Reciprocal Rank Fusion (k=60). Unit-test RRF with hand-made rankings.
4. retrieval/rerank.py: bge-reranker-v2-m3 local implementation; LLM fallback (Gemini FAST).
5. retrieval/matcher.py: full pipeline from AGENTS.md 7.1 including the batched LLM same-claim judge with Pydantic structured output (same_claim | related | different, confidence, rationale) and MATCH_THRESHOLD.
6. Gemini client wrapper (llm/client.py): first list available models and confirm the env defaults are current (not 2.5); structured output helper; retries; Langfuse tracing of every call with tokens, cost, latency. Prompts in llm/prompts/ with version strings.
7. evals/build_benchmark.py: build about 300 queries as specified in AGENTS.md section 11 (paraphrase, translation, Hinglish, forward-style, screenshot images rendered with Pillow + a Devanagari font, ~60 no-match items). Fixed seed, 70/30 dev/test split, saved under evals/data/. Add a small review CLI to inspect and correct items and mark them reviewed.
8. evals/run_evals.py: run the matcher on dev or test; compute Recall@1/5, MRR, false-match rate, no-match precision, latency, cost; write results JSON + Markdown + latest.json. Support ablation flags: --embedding, --no-rerank, --no-judge, --translate-first.
9. API endpoint POST /debug/match (dev-only, disabled in production) for manual testing.

Screenshot items are evaluated after Phase 3 adds image input; build them now, skip them in eval until then.

Done when:
- `run_evals --split dev` produces a full results file; numbers are recorded in PROGRESS.md.
- MATCH_THRESHOLD is tuned on dev only; test split numbers are reported once.
- At least one ablation comparison is recorded.
~~~

---

## Phase 3 — Input processing and claim extraction

~~~text
Read AGENTS.md (sections 6.1 steps 1–2, 8). Implement ONLY Phase 3.

Goal: any supported input becomes clean text plus a list of structured, checkable claims.

Tasks:
1. inputs/text.py: normalisation (Unicode NFC, strip zero-width/hidden characters, collapse forward boilerplate like "forwarded many times"), keep the original for display.
2. inputs/url.py: Firecrawl scrape (markdown) with trafilatura fallback; capture title, publisher, published date; store as a `sources` snapshot.
3. inputs/image.py: Gemini vision structured output (extracted text, language, quality score 0–1, notes such as "cropped" or "low resolution", visible account names/dates); pytesseract eng+hin+mar fallback; also call the Fact Check Tools image search and return candidates.
4. inputs/pdf.py: pymupdf4llm extraction with page numbers; size and page limits from AGENTS.md section 8.
5. llm/extract_claims: Gemini FAST structured output exactly per AGENTS.md 6.1 step 2 (max 4 claims; language codes en|hi|mr|hi-Latn|other; claim_type; checkworthy; entities; time_reference; text_en translation). Opinions are returned but marked not checkworthy.
6. Safety: wrap all untrusted text in delimited blocks as described in AGENTS.md section 8; add 10 injection test inputs (instructions hidden in forwards and OCR text) and assert extraction ignores them.
7. Extend run_evals to include the screenshot benchmark items now.
8. Tests with fixtures for each input type (no live calls).

Done when:
- A dev endpoint POST /debug/extract accepts text, URL, image or PDF and returns normalised text + claims.
- Hindi, Marathi, Hinglish and English samples extract correctly (show examples in PROGRESS.md).
- Injection tests pass.
~~~

---

## Phase 4 — Search providers, evidence agent, live streaming

~~~text
Read AGENTS.md (sections 6, 7.3, 8, 9 policy rule, 12). Implement ONLY Phase 4. This is the core of the project; take extra care.

Goal: a complete, bounded, observable LangGraph check pipeline that streams every step.

Tasks:
1. search/base.py interface; search/firecrawl.py (two-stage: search without scraping, then scrape selected pages; location, time filters, includeDomains as documented by Firecrawl; verify real parameter names in the official docs); search/brave.py and search/exa.py behind the same interface, enabled only when keys exist.
2. search/policy.py: presets, allow/block rules, wildcard domains (*.gov.in), strict mode, trust weights. This filter is authoritative and runs after every provider call. Unit-test thoroughly, including tricky domains (subdomains, lookalikes like gov.in.example.com).
3. search/cache.py: query cache (24 h, keyed by normalised query + policy hash) and page cache by URL with content_hash snapshots.
4. Seed system source presets (Indian government, Fact-checkers, Wire services & national media, Science & health) in supabase/seed.sql as editable defaults.
5. agent/: typed state, nodes and graph exactly as AGENTS.md 6.1 (normalize_input, extract_claims, await_confirmation via interrupt, Send fan-out per claim, match_factchecks, plan_queries, search, select_and_fetch, read_evidence, assess_sufficiency loop, compose, verify_citations, build_graph (store nodes/edges only; UI comes in Phase 7), finalize). Use the async Postgres checkpointer. propose_memories is a no-op stub until Phase 8.
6. agent/budget.py: enforce max steps, searches, pages, timeouts and cost ceiling; graceful stop with an explanation event.
7. agent/citations.py: deterministic quote verification against stored snapshots (normalised text, fuzzy ratio >= 0.9); remove unverified sentences; downgrade to INSUFFICIENT_EVIDENCE when nothing survives.
8. agent/events.py: typed events (AGENTS.md 6.1 "Live events"), published to Redis channel check:{id} and persisted to check_events.
9. Jobs and API: POST /checks (create, runs extraction, stops at confirmation), POST /checks/{id}/confirm (resume with edited/selected claims), GET /checks/{id} (full result), GET /checks/{id}/events (SSE that replays persisted events then streams live), POST /checks/{id}/rerun (new version + diff). Checks run in the arq worker.
10. Memory policy guard: a test proving that no evidence-related node receives memory content (memory is not implemented yet, but the guard and test exist now).
11. Red-team: add the injection cases from AGENTS.md section 11 (forwards, local fixture web pages served in tests, hidden text, domain steering, prompt/memory leak attempts, citation bait) and make them pass.
12. Extend run_evals: end-to-end status accuracy on benchmark items (including abstention on no-match items), citation pass rate, injection resistance, agent-path latency and cost.

Done when:
- Using curl or a tiny script you can create a check, confirm claims, watch SSE events, and get a final result with verified citations.
- Budgets stop runaway loops (test with a mocked provider that always returns irrelevant results).
- All red-team tests pass; eval results updated in PROGRESS.md.
~~~

---

## Phase 5 — Auth, app shell, design system, check pages, home, landing

~~~text
Read AGENTS.md (sections 6.3, 10 entirely, 15). Implement ONLY Phase 5. Take UX quality seriously; this is what people see first.

Goal: a polished, responsive web app where a user can sign in (or use 3 anonymous checks), run a check, watch it live and read results.

Tasks:
1. Design system: tokens.css (all colours from AGENTS.md 10.2, light + dark), Tailwind mapping, fonts via next/font (editorial serif for headings, Inter for UI, Noto Sans Devanagari for Devanagari, verified line-heights for mixed scripts), shadcn components themed to the tokens. Build a hidden /design page showing all components, status badges, stance chips and typography samples in en/hi/mr.
2. App shell: collapsible sidebar, top bar with theme toggle and a command-palette stub (wired in Phase 6), mobile bottom nav, footer with disclaimer.
3. Auth: Supabase Auth (email magic link + Google). Backend verifies tokens via JWKS. Anonymous sessions via signed cookie with ANON_CHECK_LIMIT; on sign-up, offer to claim anonymous checks. Quotas from AGENTS.md 6.3 with friendly limit messages.
4. API client: typed client from generated api-types.ts, TanStack Query hooks, SSE helper with auto-reconnect and replay.
5. New check page: Text / Link / Screenshot / PDF inputs (drag-and-drop, paste-image support), source preset selector + Strict toggle (presets from Phase 4 seed), output language toggle, sample claim chips (en/hi/mr).
6. Check result page (/check/[id]) exactly as AGENTS.md 10.4 item 4: confirm-claims step, live trace timeline (animated step entry, favicons, rejected-source reasons), result cards per claim (status badge, summary with language toggle, evidence grouped by stance with quotes and links, matched fact-check card with credited rating), "How we checked this" glass box, actions (Save → placeholder until Phase 6, Make report → placeholder until Phase 8, Re-run, View in graph → placeholder until Phase 7, Feedback → working, stored in `feedback`). Mobile: three tabs.
7. Home page (logged in): quick check, recent checks, trending fact-checks feed (corpus, language filter), simple stats.
8. Landing page (logged out): hero with quick check, sample chips, how-it-works in 3 steps, headline eval numbers read from the API (serve evals/results/latest.json via a public endpoint), disclaimer, sign-in.
9. Copy rules from AGENTS.md 10.1 everywhere (no verdict words in the app's voice).
10. Playwright smoke tests: anonymous check flow end-to-end with a mocked backend; signed-in check flow; mobile viewport run.

Done when:
- A new visitor can run a check from the landing page, confirm claims, watch the trace and read results, on desktop and on a 360 px phone viewport, in light and dark mode.
- Loading, empty and error states exist for every view in this phase.
- Lighthouse accessibility score >= 90 on landing and check pages.
~~~

---

## Phase 6 — Library

~~~text
Read AGENTS.md (sections 7.4, 10.4 item 6, 10.5). Implement ONLY Phase 6.

Goal: users can save, organise, upload and search everything, and their library becomes private evidence for future checks.

Tasks:
1. Backend: library_items, collections, tags and notes endpoints (CRUD, bulk add to collection, filters, pagination).
2. Uploads: private Supabase Storage bucket; upload endpoint with limits and MIME checks; worker job that extracts text (PDF via pymupdf4llm, images via the Phase 3 image pipeline), chunks it, embeds it into library_chunks; processing status shown in the UI.
3. Library search: hybrid search (same RRF pipeline) over the user's chunks and saved items, strictly scoped to user_id. Add a test proving no cross-user leakage.
4. Agent integration: add a read-only `search_library` step so checks can cite the user's own documents, labelled "Your document" / "From your library".
5. Wire "Save to library" on the check page (choose or create a collection, add tags, add a note).
6. Library page per AGENTS.md 10.4 item 6: grid/list toggle, filters, search bar, collections sidebar, upload drop zone with progress, item detail drawer, optimistic updates.
7. Command palette (Ctrl/⌘ + K): global search across library, checks and claims with keyboard navigation.
8. Re-run diff view on the check page (new/removed sources, changed status) using the Phase 4 rerun endpoint.
9. Tests: API tests, isolation test, Playwright flow (upload PDF → appears → searchable → used as evidence in a check with a mocked provider).

Done when:
- A user can upload a PDF, find it via search and the command palette, and see it cited in a later check.
- Collections, tags and notes work on desktop and mobile.
~~~

---

## Phase 7 — Claim graph and timeline

~~~text
Read AGENTS.md (sections 5 graph tables, 6.1 build_graph, 10.4 item 5). Implement ONLY Phase 7.

Goal: an interactive, beautiful, fast graph of the user's claims, sources, fact-checks, entities and documents.

Tasks:
1. Backend: graph endpoints: whole-library graph with filters (node type, date range, collection, status), per-check subgraph, node detail; edge update (relabel, delete → stored as feedback with origin=user); accept or dismiss `similar_to` suggestions.
2. claimgraph/linking.py: compute similar_to suggestions between a new claim and the user's past claims (SIMILAR_CLAIM_THRESHOLD); entity merge rules (same entity, different spellings or scripts, e.g. "मोदी" / "Modi") using normalisation + embedding similarity, with a conservative threshold.
3. Frontend graph page: Cytoscape.js with fcose layout, lazy-loaded bundle; node styles by type (icons or shapes + labels), edge styles by type exactly as AGENTS.md 10.4 item 5 (always paired with legend labels, not colour alone); filters panel; search; click → side panel with details, links and actions; zoom/fit controls; export current view as PNG (needed by reports in Phase 8).
4. Per-claim timeline view: earliest source date found → fact-check dates → user's check date, with tooltips and links.
5. Accessible List view toggle showing the same nodes and relations as an expandable list.
6. "View in graph" from the check page opens the graph focused on that check's subgraph.
7. Performance: smooth interaction with 500 nodes (test with generated data); progressive rendering for larger graphs.
8. Tests: linking logic unit tests, API tests, Playwright test for filter + click + relabel edge.

Done when:
- After 5+ checks, the graph clearly shows related claims, shared sources and suggested links; edge corrections persist.
- Works in light/dark mode and has a usable layout on mobile (graph full screen, panel as bottom sheet).
~~~

---

## Phase 8 — Sources page, memory, settings, reports

~~~text
Read AGENTS.md (sections 2.5, 9, 10.4 items 7–9 and 11, 8.6). Implement ONLY Phase 8.

Goal: users can tune their sources, control what the app remembers, and produce shareable reports.

Tasks:
1. Sources page: system presets shown as editable copies; custom presets CRUD; domain rules table (allow/block, trust weight slider 0.5–1.5); "test a domain" helper that runs a URL through search/policy.py and explains the result; default preset and strict default saved to the profile.
2. Memory with LangMem on the LangGraph Postgres store, namespace ("memories", user_id), wrapped by our `memories` table with status pending → active → rejected. Implement propose_memories in the agent (only the allowed kinds in AGENTS.md section 9, with an evidence string). Inline toast for new suggestions plus the Memory tab in Settings (approve, reject, edit, delete, clear all, export). Deleting removes from both our table and the LangMem store.
3. memory/policy.py: only compose, reports and UI suggestion code paths can read active memories; enforce with a node allowlist; extend the Phase 4 guard test; add the memory-bias eval (same claims, with and without viewpoint-style memories → identical statuses and evidence sets).
4. Settings: Profile, Preferences (language, report style, default preset, strict default), Memory, Data (export all as JSON, delete account with confirmation).
5. Reports backend: generate from a check or a collection with Gemini PRO into a structured schema (title, summary, claims table, evidence per claim with citation ids, methodology & limitations, sources list), then render to Markdown; citations reuse already-verified quotes only; report style (brief/detailed) from profile/memory; WeasyPrint PDF via a Jinja2 template using the same design tokens and fonts (test Devanagari rendering in the PDF); Markdown export; share token (off by default) and a public read-only endpoint.
6. Reports frontend: list page; editor page with Markdown editor + live preview; insert graph snapshot (PNG from the Phase 7 export); export PDF/MD buttons; share toggle with copy-link; public /share/[token] page (clean, printable, disclaimer, no app chrome beyond a small header).
7. Wire "Make report" on the check page and on collections.
8. Tests: policy tests, memory lifecycle tests, report schema tests, PDF render smoke test (en/hi/mr), Playwright flow (check → report → edit → export → share link opens logged out).

Done when:
- A user can approve a memory and see it change output language/report style but never statuses or evidence (bias eval passes).
- A report with a graph snapshot exports to a good-looking PDF with correct Devanagari text, and the share link works only when enabled.
~~~

---

## Phase 9 — Polish, evals report, About page, deploy, case study

~~~text
Read AGENTS.md (sections 10.5, 11, 15). Implement ONLY Phase 9.

Goal: production-quality finish, public deployment, and portfolio-ready documentation.

Tasks:
1. UX polish pass on every page: spacing, typography, empty/loading/error states, micro-interactions, focus states, mobile layouts, dark mode, copy review against the banned-words rule (add an automated test that scans en.json and LLM templates for banned verdict words in the app's own voice).
2. Accessibility audit (axe via Playwright on all main pages; fix every serious issue) and performance pass (bundle analysis, lazy-load heavy components, image optimisation).
3. Admin feedback page (/admin/feedback, ADMIN_EMAILS only): filters, resolve, "export as eval cases" into evals/data/feedback_cases.json.
4. Final evals: run the full test split once; all ablations; red-team; memory-bias; produce evals/results/latest.json and a clear Markdown report with tables and a short failure analysis (10 representative failures with causes).
5. About / How it works page: architecture diagram, agent flow diagram, eval tables and charts from latest.json, limitations, credits to fact-checkers and data providers.
6. Rate limiting and quota review; TRACE_CONTENT=false in production; security headers; CORS locked to the app domain.
7. Deploy: web to Vercel; api + worker to Render or Railway via Docker; Redis (Upstash or host); hosted Supabase with migrations applied; daily ingestion cron running; environment variables documented. Note in DECISIONS.md the embedding backend used in production and re-index if it differs from local.
8. README.md as a portfolio case study: problem, constraints, architecture diagram, key decisions (pipeline vs agent, two-stage search, citation verification, memory policy, evidence-not-verdicts), results table, limitations, screenshots/GIFs, how to run locally, live demo link.
9. Seed a demo account with 6–8 good example checks, a collection and a report for recruiters to explore.

Done when:
- The live site works end-to-end for a new visitor and a signed-in user on desktop and phone.
- CI green; evals report and About page published; README reads as a complete case study.
~~~

---

## Useful follow-up prompts (any phase)

- **Review:** "Review the code from Phase N against AGENTS.md. List deviations, missing tests and risky parts, then fix them in small commits."
- **Debug:** "This is failing: <error/log>. Find the root cause before changing code; explain it in 3 lines, then fix it and add a regression test."
- **UX check:** "Walk through <page> as a first-time user on a phone in dark mode. List every confusing, ugly or slow moment, then fix the top 5."
- **Cost check:** "Show average tokens, cost and latency per node from Langfuse for the last 20 checks and propose the top 3 optimisations."

# How to run the Elenchus prototype

A quick, throwaway prototype: paste text → it extracts claims, searches the web,
shows cited evidence (never a verdict), draws a claim/source graph, and remembers
your output language for the session.

> **You don't need any API keys to try it.** With no keys it runs in **mock mode**
> and the whole flow works on demo data. Add keys later for real results.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | the backend |
| uv | latest | Python package manager — `pip install uv` if you don't have it |
| Node.js | 20+ | the frontend |
| pnpm | 10.x | `npm install -g pnpm@10` (the repo pins pnpm 10.33.0) |

---

## 2. Get the code

```bash
git clone -b prototype https://github.com/Deep-Arande/Elenchus.git
cd Elenchus
```

(Or unzip the archive you were sent and `cd` into it.)

---

## 3. Start the backend (API)

```bash
cd apps/api
uv sync                 # creates a .venv and installs dependencies
uv run uvicorn elenchus.main:app --reload --port 8000
```

Leave this running. It serves the API on **http://localhost:8000**.

> **Windows PowerShell notes**
> - PowerShell doesn't accept `&&` — run commands on separate lines.
> - If `uv` isn't found, use the venv directly instead:
>   `.\.venv\Scripts\uvicorn.exe elenchus.main:app --reload --port 8000`

---

## 4. Start the frontend (web)

In a **second terminal**:

```bash
cd apps/web
pnpm install
pnpm dev
```

Open **http://localhost:3000** and click **“Check a claim”** (or go to `/try`).

---

## 5. (Optional) Real results instead of mock

By default it uses mock data. For real Gemini + Firecrawl results, create
`apps/api/.env` with your own keys:

```
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL_FAST=gemini-flash-lite-latest
GEMINI_MODEL_MAIN=gemini-3.5-flash
FIRECRAWL_API_KEY=your-firecrawl-key
```

Then restart the backend. (No database is needed — everything is in memory.)

- Gemini keys: https://aistudio.google.com/apikey
- Firecrawl keys: https://www.firecrawl.dev

---

## 6. Try it

1. Paste a message, or click a sample chip (English / Hindi / Marathi).
2. Hit **Extract claims**, untick anything you don't want, then **Check**.
3. Watch the live trace, read the evidence cards, explore the graph.
4. Toggle light/dark in the header; switch output language (remembered for the session).

---

## Troubleshooting

- **`&&` error in PowerShell** → run the two commands on separate lines.
- **`uv` not recognized** → `pip install uv`, or use `.\.venv\Scripts\uvicorn.exe …`.
- **pnpm wants to upgrade / `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`** → the repo
  pins pnpm 10.33.0; run `corepack disable` then `pnpm install`, or
  `npm install -g pnpm@10`.
- **Gemini `503 UNAVAILABLE`** → that model is busy; it auto-retries. If it
  persists, change `GEMINI_MODEL_MAIN` in `apps/api/.env` to
  `gemini-3.1-flash-lite` and restart.
- **Web can't reach the API** → make sure the backend is running on port 8000
  (the web app defaults to `http://localhost:8000`).

---

_This is a research demo. It surfaces evidence; it does not give verdicts.
Always read the sources._

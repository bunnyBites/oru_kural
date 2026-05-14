# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Oru Kural (ஒரு குரல்) is a civic tech dashboard that scrapes tweets mentioning the Tamil Nadu CM's X handle (@CMOTamilnadu), categorizes them with Gemini AI, and displays them in a web UI. Three independent sub-projects in one repo — no shared Cargo workspace.

## Commands

### Scripts (Python — run from `scripts/`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scrape_tweets.py                        # full Apify run → Supabase upsert
python scrape_tweets.py --dry-run file.json    # skip Apify, load local JSON instead
python categorize_tweets.py                    # Gemini batch categorization
```

### Backend (Rust — run from `backend/`)
```bash
cargo check
cargo build
cargo run          # requires DATABASE_URL in .env; listens on PORT (default 3000)
```

### Frontend (Dioxus — run from `frontend/`)
```bash
# Terminal 1 — Tailwind (Tailwind v4, @tailwindcss/cli)
npm run css        # alias for: npx @tailwindcss/cli -i input.css -o assets/tailwind.css --watch

# Terminal 2 — Dioxus dev server
dx serve           # serves at http://localhost:8080
```

## Architecture

```
scripts/          Python async pipeline (httpx, no requests library)
  scrape_tweets.py      Apify → map_item() → Supabase upsert (batches of 100)
  categorize_tweets.py  Supabase fetch → Gemini Flash 2.0 → Supabase patch (batches of 40)

backend/          Rust + Axum REST API
  src/models.rs         Tweet, CategoryStat, Stats (sqlx::FromRow + serde::Serialize)
  src/handlers.rs       Four route handlers; all use sqlx runtime queries (no macros)
  src/main.rs           AppState{db: PgPool}, router, CORS

frontend/         Rust + Dioxus 0.7 (compiles to WASM)
  src/api.rs            Types (Tweet, Stats) + reqwest fetch functions; BACKEND = localhost:3000
  src/views/home.rs     Stats bar, category pills (use_signal), tweet grid (use_resource)
  src/views/detail.rs   Single tweet view with link back to X
  src/main.rs           Route enum (Routable), App mounts stylesheet + Router
  assets/tailwind.css   Generated — never edit by hand
```

## Key design decisions

**Single source of truth for schema** — `tweets` table columns are defined once in Supabase. The Python scripts, Axum models, and Dioxus API types all mirror the same shape; keep them in sync manually if the schema changes.

**Backend uses Supabase REST API** — no direct Postgres connection. `AppState` holds a `reqwest::Client` + `SUPABASE_URL` + `SUPABASE_ANON_KEY`. The `auth()` helper in `handlers.rs` attaches the required `apikey` and `Authorization` headers to every request. The `/api/stats` handler fetches all rows' `(category, scraped_at)` columns and aggregates in Rust — acceptable at ≤500 rows; revisit if volume grows.

**Dioxus reactivity pattern** — In `home.rs`, `use_resource` reads `selected` (a `Signal`) in the *synchronous* part of its closure before the `async move` block. This is what makes the tweet list re-fetch when the category filter changes.

**Tailwind v4** — CSS configuration lives in `input.css` (`@source` directive), not `tailwind.config.js`. The `@tailwindcss/cli` package is required (the `tailwindcss` package alone has no binary in v4).

**tweet `id` is the X tweet ID** (text primary key) — upsert on `id` deduplicates re-runs automatically. Confidence is `float4` (0.0–1.0) from Gemini.

**LLM abstraction** — All classification calls go through `scripts/llm.py:classify_tweets()`. Never call `google-generativeai` or any LLM SDK directly from `categorize_tweets.py`. To switch to OpenRouter, set `OPENROUTER_API_KEY` in `.env` — no code changes needed.

**Supabase key split** — Python scripts use `SUPABASE_SERVICE_ROLE_KEY` for all writes (INSERT/UPDATE). Reads use `SUPABASE_ANON_KEY`. The Axum backend uses `DATABASE_URL` (direct Postgres) and never touches the Supabase REST API or either key.

## Environment variables

All vars live in `.env` (copy from `.env.example`):

| Variable | Used by |
|---|---|
| `APIFY_API_KEY` | `scrape_tweets.py` |
| `SUPABASE_URL` | both Python scripts (REST API) |
| `SUPABASE_ANON_KEY` | Python scripts — reads only |
| `SUPABASE_SERVICE_ROLE_KEY` | Python scripts — writes only; never in frontend |
| `GEMINI_API_KEY` | `llm.py` (Gemini backend) |
| `GEMINI_MODEL` | `llm.py` — defaults to `gemini-2.5-flash` |
| `OPENROUTER_API_KEY` | `llm.py` — optional; presence switches LLM provider |
| `OPENROUTER_MODEL` | `llm.py` — optional; defaults to `google/gemini-2.5-flash` |
| `PORT` | `backend` (optional, defaults to 3000) |

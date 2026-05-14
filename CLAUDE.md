# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Oru Kural (ஒரு குரல்) is a civic tech dashboard that scrapes tweets mentioning the Tamil Nadu CM's X handle (@CMofTamilNadu), categorizes them with Gemini AI, and displays them in a web UI. Three independent sub-projects in one repo — no shared Cargo workspace.

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

**sqlx runtime queries** — `backend` uses `sqlx::query_as::<_, T>(sql).bind(...)` (not the `query!` macro) so `DATABASE_URL` is not required at compile time.

**Dioxus reactivity pattern** — In `home.rs`, `use_resource` reads `selected` (a `Signal`) in the *synchronous* part of its closure before the `async move` block. This is what makes the tweet list re-fetch when the category filter changes.

**Tailwind v4** — CSS configuration lives in `input.css` (`@source` directive), not `tailwind.config.js`. The `@tailwindcss/cli` package is required (the `tailwindcss` package alone has no binary in v4).

**tweet `id` is the X tweet ID** (text primary key) — upsert on `id` deduplicates re-runs automatically. Confidence is `float4` (0.0–1.0) from Gemini.

## Environment variables

All vars live in `.env` (copy from `.env.example`):

| Variable | Used by |
|---|---|
| `APIFY_API_KEY` | `scrape_tweets.py` |
| `SUPABASE_URL` | both Python scripts (REST API) |
| `SUPABASE_ANON_KEY` | both Python scripts (REST API) |
| `GEMINI_API_KEY` | `categorize_tweets.py` |
| `DATABASE_URL` | `backend` (direct Postgres, must include `?sslmode=require`) |
| `PORT` | `backend` (optional, defaults to 3000) |

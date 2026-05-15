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
  scrape_tweets.py      X API v2 → signals table (MAX_PAGES via X_MAX_PAGES env, default 3)
  scrape_reddit.py      Reddit JSON → signals table
  scrape_cm_events.py   RSS → cm_events table
  categorize_signals.py Gemini categorization of all signals
  cluster_issues.py     Gemini clustering → issues table
  link_events_to_issues.py  Gemini links cm_events ↔ issues

backend/          Rust + Axum REST API (Supabase REST proxy)
  src/models.rs         Signal, Issue, CmEvent, CategoryStat + response envelopes
  src/handlers.rs       6 handlers: health, list_issues, get_issue, list_signals, list_events, get_stats
  src/main.rs           AppState{client, supabase_url, supabase_key}, router, CORS via FRONTEND_ORIGIN

  Routes (no /api/ prefix):
    GET /health          → { status, service }
    GET /issues          → PagedResponse<Issue>  (status, category, location, limit, cursor)
    GET /issues/:id      → { issue, signals, linked_event }
    GET /signals         → PagedResponse<Signal> (source, category, q, limit, cursor)
    GET /events          → PagedResponse<CmEvent>(category, linked, limit, cursor)
    GET /stats           → { data: Vec<CategoryStat> }

frontend/         Rust + Dioxus 0.7 (compiles to WASM)
  src/api.rs            fetch_issues, fetch_issue_detail, fetch_events, fetch_stats
                        API_BASE from option_env!("API_BASE_URL"), default localhost:8080
  src/models.rs         Signal, Issue, CmEvent, CategoryStat, Tab, format_date()
  src/components/
    app_shell.rs        Root — provides AppCtx{active_tab, dark_mode} via context
    header.rs           Brand + tab nav + dark mode toggle
    issues_board.rs     Tab 1 — issues grid with filters, pagination, detail panel
    filter_bar.rs       Status + category pills + search input
    issue_card.rs       Issue card (3-section flex layout, animate-card-enter)
    issue_detail.rs     Expanded view — signals + linked CM event
    events_feed.rs      Tab 2 — CM events list with linked-only filter
    event_card.rs       Event card
    stats_panel.rs      Tab 3 — category breakdown fetched from /stats
    signal_card.rs      Signal card (used inside issue_detail)
    skeleton_card.rs    Shimmer loading placeholder (3-section layout)
    status_badge.rs     Status pill with inline style colors
    category_badge.rs   Category pill with inline style colors
    source_badge.rs     X / Reddit source indicator
  assets/tailwind.css   Generated — never edit by hand
  input.css             Tailwind v4 config: @import, @theme, @layer base, animations
```

## Key design decisions

**Schema tables** — `signals` (unified X + Reddit), `issues` (clustered demands), `cm_events` (CM press releases), `signal_issue_map`, `category_stats`, `scrape_runs`. Never re-create these migrations (001–006 already applied).

**Backend is a thin Supabase proxy** — no direct Postgres connection, no business logic. `AppState` holds `reqwest::Client` + bare Supabase project URL + anon key. The `auth()` helper attaches `apikey` + `Authorization` headers to every PostgREST request. All pagination is keyset (no OFFSET, no COUNT(*)).

**Dioxus reactivity pattern** — `use_effect` reads filter signals synchronously before spawning async fetch. Reading signals inside `use_effect` closure body creates subscriptions; reading inside `spawn(async move {...})` does not. This makes filter changes auto-trigger refetches.

**Dark mode** — toggled via `document.documentElement.setAttribute('data-theme','dark')`, persisted in `localStorage`. AppCtx provides `dark_mode: Signal<bool>` via context; Header reads it and applies the JS via `document::eval()`.

**Global state** — `AppCtx { active_tab, dark_mode }` provided at AppShell via `use_context_provider`. Each tab (IssuesBoard, EventsFeed, StatsPanel) owns its own data signals locally — no prop drilling of data.

**Tailwind v4** — CSS config in `input.css` (`@import "tailwindcss"` first line, `@source`, `@theme` for custom tokens). No `tailwind.config.js`. All status/category/brand colors use inline `style=` in components (dynamic classes not purged at build time).

**LLM abstraction** — All classification calls go through `scripts/llm.py:classify_tweets()`. Never call `google-generativeai` directly. Set `OPENROUTER_API_KEY` to switch providers without code changes.

**Supabase key split** — Python scripts use `SUPABASE_SERVICE_ROLE_KEY` for writes, `SUPABASE_ANON_KEY` for reads. Axum backend uses only `SUPABASE_ANON_KEY` (read-only).

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
| `PORT` | `backend` (optional, defaults to 8080) |
| `FRONTEND_ORIGIN` | `backend` — CORS allowed origin; omit to use permissive CORS in dev |
| `API_BASE_URL` | `frontend` — compile-time backend URL; defaults to `http://localhost:8080` |

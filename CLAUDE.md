# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Oru Kural (ஒரு குரல்) is a civic tech dashboard that scrapes public posts mentioning `@CMOTamilnadu` from X and Reddit, clusters them into civic issues with Gemini AI, tracks official CM press releases, and displays everything in a three-tab web UI. Three independent sub-projects in one repo — no shared Cargo workspace.

## Commands

### Scripts (Python — run from `scripts/`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full pipeline — run in this order:
python scrape_tweets.py        # X API v2 → signals table (X_MAX_PAGES env, default 3, prod 10)
python scrape_reddit.py        # Reddit JSON → signals table
python scrape_cm_events.py     # TN Gov + The Hindu RSS → cm_events table
python categorize_signals.py   # Gemini batch categorization of all uncategorized signals
python cluster_issues.py       # Gemini semantic clustering → issues table
python link_events_to_issues.py # Gemini links cm_events ↔ issues

# Dry-run (skip X API, load local JSON instead):
python scrape_tweets.py --dry-run path/to/file.json
```

### Backend (Rust — run from `backend/`)
```bash
cargo check
cargo build
cargo run    # reads .env from repo root via dotenvy; listens on PORT (default 3000 via .env)
```

### Frontend (Dioxus — run from `frontend/`)
```bash
# Terminal 1 — Tailwind v4 (watch mode)
npm run css   # npx @tailwindcss/cli -i input.css -o assets/tailwind.css --watch

# Terminal 2 — Dioxus dev server (port 8080)
dx serve      # → http://localhost:8080

# Production build (set API_BASE_URL before building):
API_BASE_URL=https://oru-kural-backend.fly.dev dx build --release
```

## Architecture

```
scripts/          Python async pipeline (httpx — never use requests library)
  scrape_tweets.py      X API v2 → signals table
  scrape_reddit.py      Reddit JSON fallback → signals table
  scrape_cm_events.py   RSS → cm_events table
  categorize_signals.py Gemini categorization of all signals (batch 40)
  cluster_issues.py     Gemini clustering → issues table
  link_events_to_issues.py  Gemini links cm_events ↔ issues
  categorize_tweets.py  Legacy v2 script — kept for reference, not in active pipeline
  classifier_rules.py   Rule-based pre-classifier utilities
  llm.py                LLM abstraction — all Gemini calls go through here

backend/          Rust + Axum REST API (Supabase REST proxy)
  src/models.rs         Signal, Issue, CmEvent, CategoryStat + response envelopes
  src/handlers.rs       6 handlers: health, list_issues, get_issue, list_signals, list_events, get_stats
  src/main.rs           AppState{client, supabase_url, supabase_key}, router, CORS via FRONTEND_ORIGIN

  Routes (no /api/ prefix):
    GET /health          → { status, service }
    GET /issues          → PagedResponse<Issue>  (status, category, location, limit, cursor)
    GET /issues/:id      → { issue, signals[], linked_event? }
    GET /signals         → PagedResponse<Signal> (source, category, q, limit, cursor)
    GET /events          → PagedResponse<CmEvent>(category, linked, limit, cursor)
    GET /stats           → { data: Vec<CategoryStat> }

frontend/         Rust + Dioxus 0.7 (compiles to WASM)
  src/api.rs            fetch_issues, fetch_issue_detail, fetch_events, fetch_stats
                        API_BASE from option_env!("API_BASE_URL"), default http://localhost:3000
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

**Schema tables** — `signals` (unified X + Reddit), `issues` (clustered demands), `cm_events` (CM press releases), `signal_issue_map`, `category_stats`, `scrape_runs`. Never re-create these migrations (001–008 already applied).

**RLS policies** — Supabase has Row Level Security enabled on all tables. Migration `008_anon_read_policies.sql` adds `SELECT` policies for the `anon` role on `signals`, `issues`, `cm_events`, `category_stats`, `signal_issue_map`. Without this migration the backend (which uses `SUPABASE_ANON_KEY`) returns empty arrays even when rows exist. Service role key bypasses RLS.

**Backend is a thin Supabase proxy** — no direct Postgres connection, no business logic. `AppState` holds `reqwest::Client` + bare Supabase project URL + anon key. The `auth()` helper attaches `apikey` + `Authorization` headers to every PostgREST request. All pagination is keyset (no OFFSET, no COUNT(*)).

**Local dev port split** — backend runs on `:3000` (set via `PORT=3000` in `.env`), Dioxus dev server runs on `:8080`. The frontend `API_BASE` defaults to `http://localhost:3000`. Do not run the backend on `:8080` locally; it will conflict with `dx serve` and the frontend will receive HTML instead of JSON. In production (Fly.io), the backend runs on `:8080` — set `API_BASE_URL` at Vercel build time.

**Dioxus reactivity pattern** — `use_effect` reads filter signals synchronously before spawning async fetch. Reading signals inside `use_effect` closure body creates subscriptions; reading inside `spawn(async move {...})` does not. This makes filter changes auto-trigger refetches.

**Dark mode** — toggled via `document.documentElement.setAttribute('data-theme','dark')`, persisted in `localStorage`. AppCtx provides `dark_mode: Signal<bool>` via context; Header reads it and applies the JS via `document::eval()`. CSS `data-theme` dark variables are not yet fully wired — this is a known gap.

**Global state** — `AppCtx { active_tab, dark_mode }` provided at AppShell via `use_context_provider`. Each tab (IssuesBoard, EventsFeed, StatsPanel) owns its own data signals locally — no prop drilling of data.

**Tailwind v4** — CSS config in `input.css` (`@import "tailwindcss"` first line, `@source`, `@theme` for custom tokens). No `tailwind.config.js`. All status/category/brand colors use inline `style=` in components (dynamic classes not purged at build time). Never add dynamic Tailwind classes; use `style=` instead.

**LLM abstraction** — All classification calls go through `scripts/llm.py`. Never call `google-generativeai` directly. Set `OPENROUTER_API_KEY` to switch providers without code changes.

**Supabase key split** — Python scripts use `SUPABASE_SERVICE_ROLE_KEY` for writes, `SUPABASE_ANON_KEY` for reads. Axum backend uses only `SUPABASE_ANON_KEY` (read-only). Never put service role key in frontend or backend.

## Environment variables

All vars live in `.env` at the repo root (copy from `.env.example`). `dotenvy` in the backend reads from the root, not from `backend/`.

| Variable | Used by | Notes |
|---|---|---|
| `SUPABASE_URL` | Python scripts, backend | Project URL (no trailing slash) |
| `SUPABASE_ANON_KEY` | Python scripts (reads), backend | Publishable — safe in backend |
| `SUPABASE_SERVICE_ROLE_KEY` | Python scripts (writes only) | Secret — never in backend or frontend |
| `GEMINI_API_KEY` | `llm.py` | Google AI Studio key |
| `GEMINI_MODEL` | `llm.py` | Defaults to `gemini-2.5-flash` |
| `OPENROUTER_API_KEY` | `llm.py` | Optional; presence switches LLM provider |
| `OPENROUTER_MODEL` | `llm.py` | Optional; defaults to `google/gemini-2.5-flash` |
| `X_BEARER_TOKEN` | `scrape_tweets.py` | X API v2 app-only bearer token |
| `X_MAX_PAGES` | `scrape_tweets.py` | Pages to fetch; default 3, set 10 in prod |
| `PORT` | Backend | `3000` in local `.env`; `8080` on Fly.io |
| `FRONTEND_ORIGIN` | Backend | CORS allowed origin; omit for permissive CORS in dev |
| `API_BASE_URL` | Frontend (compile-time) | Backend URL baked in at `dx build`; defaults to `http://localhost:3000` |

## Supabase migrations

Applied in order (never re-run):

| File | What it does |
|---|---|
| `002_scale_indexes_and_scrape_runs.sql` | Indexes + scrape_runs table |
| `003_category_stats.sql` | category_stats table |
| `004_retention_archive.sql` | Archival/retention rules |
| `005_categorization_failures.sql` | Failure tracking table |
| `006_v3_schema.sql` | issues, cm_events, tweet_issue_map, functions |
| `007_signals_table.sql` | signals table (replaces tweets), signal_issue_map |
| `008_anon_read_policies.sql` | RLS SELECT policies for anon role — required for backend reads |

## Automation (GitHub Actions)

`.github/workflows/weekly_scrape.yml` runs every Monday at 2am UTC. Required GitHub secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `X_BEARER_TOKEN`. Trigger manually via **Actions → Weekly Tweet Scraper → Run workflow**.

## Do NOT touch

- `scripts/scrape_tweets_apify.py` — frozen legacy Apify scraper
- `supabase/migrations/` — migrations 002–008 are already applied; never re-create or drop tables
- `frontend/assets/tailwind.css` — generated file, always regenerate with `npm run css`

## Known gaps / future work

These are not done and are safe to implement:

- **Dark mode CSS** — `data-theme` toggle is wired but the dark-mode CSS variables in `input.css` are incomplete. Need to fill in `[data-theme="dark"]` overrides for all `--tvk-*` tokens.
- **Error toasts** — API call failures in the frontend only log to `eprintln!`. Should surface a user-visible error message (Dioxus toast or inline error state).
- **Frontend API retry** — no retry on transient network failures in `api.rs`. A simple exponential backoff with 2–3 attempts would help.
- **Structured logging in backend** — `eprintln!` only. Replace with `tracing` + `tracing-subscriber` for structured logs that Fly.io can stream.
- **Backend tests** — zero `#[test]` functions. At minimum, test handler deserialization against Supabase response shapes.
- **Rate limiting** — backend has no rate limiting. Add `tower_governor` middleware before any public launch.
- **Reddit OAuth** — `scrape_reddit.py` uses unauthenticated JSON fallback. Wire up `REDDIT_CLIENT_ID/SECRET` when API access is approved.
- **`issues` table needs pipeline to run** — the Issues Board tab stays empty until `cluster_issues.py` has been run at least once. This is expected behavior, not a bug.
- **GitHub Actions workflow gap** — `weekly_scrape.yml` step 2 still references `categorize_tweets.py` (v2 legacy). The active v3 categorizer is `categorize_signals.py` (step 5 in the same workflow). The legacy step is harmless but redundant.

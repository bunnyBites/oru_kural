# Oru Kural — Project Structure

Three independent sub-projects in one repo. No shared Cargo workspace.
v4 additions are marked with `[v4]`.

---

## Top-level

```
oru_kural/
├── scripts/          Python async data pipeline
├── backend/          Rust + Axum REST API
├── frontend/         Rust + Dioxus 0.7 (WASM)
├── supabase/
│   └── migrations/   SQL migration files (001–009 applied; 010 pending [v4])
├── .github/
│   └── workflows/
│       ├── weekly_scrape.yml     Monday 2am UTC pipeline run
│       └── deploy_backend.yml    Auto-deploy backend on push to main
├── .env.example      All required env vars with comments
├── CLAUDE.md         AI coding agent instructions
├── roadmap.md        [v4] v4 milestones and goals
├── approach.md       [v4] Technical design decisions
├── structure.md      [v4] This file
├── tasks.md          v1–v3 task tracker (22/23 done)
├── fly.toml          Fly.io backend deployment config
├── vercel.json       Vercel frontend deployment config
└── Dockerfile        Backend container image
```

---

## scripts/

```
scripts/
├── scrape_tweets.py          X API v2 → signals table (source="x")
│                             [v4 TODO] migrate to twscrape
├── scrape_reddit.py          Reddit JSON fallback → signals table (source="reddit")
│                             [T-11 blocked] wire up PRAW OAuth when approved
├── scrape_cm_events.py       TN Gov + The Hindu RSS → cm_events table
│                             Gemini enrichment: location, department, category
├── scrape_grievances.py      [v4] CM Helpline + GCC PGR aggregate stats
│                             → synthetic signals (source="cm_helpline" / "gcc_pgr")
├── scrape_instagram.py       [v4 TODO] CMO Instagram → cm_events (instaloader)
├── scrape_telegram.py        [v4 TODO] public district Telegram channels → signals (telethon)
├── categorize_signals.py     Gemini batch categorization of all uncategorized signals
│                             Runs classifier_rules.py first (rule-based pre-classifier)
├── cluster_issues.py         Gemini semantic clustering → issues table
│                             [v4 TODO] add Tamil pass after new issues are created
├── link_events_to_issues.py  Gemini links cm_events ↔ issues (confidence ≥ 0.7)
├── llm.py                    LLM abstraction — all Gemini calls go here
│                             OPENROUTER_API_KEY presence switches provider
├── classifier_rules.py       Keyword-based pre-classifier (do not modify)
├── categorize_tweets.py      Legacy v2 script — kept for reference (do not modify)
├── scrape_tweets_apify.py    Frozen Apify scraper (do not modify)
├── requirements.txt          httpx[asyncio], python-dotenv, google-genai, feedparser
│                             [v4 TODO] add twscrape, instaloader, telethon
└── run_pipeline.sh           Local convenience script — runs full pipeline in order
```

### Pipeline execution order

```
scrape_tweets.py        →  X signals
scrape_reddit.py        →  Reddit signals
scrape_cm_events.py     →  CM events (RSS)
scrape_grievances.py    →  Grievance synthetic signals   [v4, done]
  ↓
categorize_signals.py   →  Categorize all new signals
  ↓
cluster_issues.py       →  Cluster signals into issues
  ↓
link_events_to_issues.py→  Link CM events to open issues
```

---

## backend/

```
backend/
├── src/
│   ├── main.rs         AppState, router, middleware stack
│   │                   Middleware (in order): SetRequestId, TraceLayer, PropagateRequestId,
│   │                   Compression, CORS, Governor (rate limiting)
│   ├── handlers.rs     6 route handlers + fetch_json<T> helper (10s Supabase timeout)
│   │   ├── health      GET /health
│   │   ├── list_issues GET /issues    (status, category, location, search_query, limit, cursor)
│   │   ├── get_issue   GET /issues/:id
│   │   ├── list_signals GET /signals  (source, category, q, limit, cursor)
│   │   ├── list_events GET /events    (category, linked, limit, cursor)
│   │   └── get_stats   GET /stats
│   └── models.rs       Signal, Issue, CmEvent, CategoryStat, PagedResponse, HealthResponse
├── Cargo.toml
└── .env                Symlink or copy from repo root (dotenvy reads from root)
```

**Routes (no /api/ prefix):**

| Method | Path | Response |
|---|---|---|
| GET | /health | `{ status, service }` |
| GET | /issues | `PagedResponse<Issue>` |
| GET | /issues/:id | `{ issue, signals[], linked_event? }` |
| GET | /signals | `PagedResponse<Signal>` |
| GET | /events | `PagedResponse<CmEvent>` |
| GET | /stats | `{ data: Vec<CategoryStat> }` |

---

## frontend/

```
frontend/
├── src/
│   ├── main.rs             Entry point
│   ├── api.rs              fetch_* functions; API_BASE from option_env!("API_BASE_URL")
│   ├── models.rs           Signal, Issue, CmEvent, CategoryStat, Tab, format_date()
│   │                       [v4 TODO] add title_ta, summary_ta fields to Issue
│   └── components/
│       ├── app_shell.rs    Root — AppCtx{active_tab, dark_mode} via context
│       │                   [v4 TODO] add tamil_mode: Signal<bool> to AppCtx
│       ├── header.rs       Brand + tab nav + dark mode toggle
│       │                   [v4 TODO] add Tamil/English toggle button
│       ├── issues_board.rs Tab 1 — issues grid, filters, pagination, detail panel
│       ├── filter_bar.rs   Status + category pills + search (300ms debounce)
│       ├── issue_card.rs   Issue card (animate-card-enter CSS animation)
│       │                   [v4 TODO] render title_ta / summary_ta when tamil_mode
│       ├── issue_detail.rs Expanded view — signals + linked CM event
│       ├── events_feed.rs  Tab 2 — CM events list
│       ├── event_card.rs   Event card
│       ├── stats_panel.rs  Tab 3 — category breakdown from /stats
│       ├── signal_card.rs  Signal card (used in issue_detail)
│       │                   [v4 TODO] show content vs translated_content per tamil_mode
│       ├── skeleton_card.rs Shimmer loading placeholder
│       ├── status_badge.rs  Status pill (badge-status-* CSS classes)
│       ├── category_badge.rs Category pill (badge-* CSS classes)
│       └── source_badge.rs  X / Reddit / Grievance source indicator
│                            [v4 TODO] add cm_helpline and gcc_pgr variants
├── assets/
│   └── tailwind.css        Generated — never edit by hand
├── input.css               Tailwind v4 config (@import, @theme, @layer base, animations)
└── Dioxus.toml
```

---

## supabase/migrations/

| File | Status | What it does |
|---|---|---|
| `002_scale_indexes_and_scrape_runs.sql` | Applied | Indexes + scrape_runs table |
| `003_category_stats.sql` | Applied | category_stats table |
| `004_retention_archive.sql` | Applied | Archival/retention rules |
| `005_categorization_failures.sql` | Applied | Failure tracking table |
| `006_v3_schema.sql` | Applied | issues, cm_events, signal_issue_map |
| `007_signals_table.sql` | Applied | signals table (replaces tweets) |
| `008_anon_read_policies.sql` | Applied | RLS SELECT policies for anon role |
| `009_dedup_and_duplicate.sql` | Applied | UNIQUE INDEX on signal_issue_map; duplicate_of column |
| `010_tamil_columns.sql` | **TODO** | `title_ta TEXT`, `summary_ta TEXT` on issues |

Never re-run or modify 002–009. Migration 010 must be applied before the Tamil UI goes live.

---

## Environment variables

| Variable | Used by | Notes |
|---|---|---|
| `SUPABASE_URL` | Scripts, backend | Project URL, no trailing slash |
| `SUPABASE_ANON_KEY` | Scripts (reads), backend | Publishable |
| `SUPABASE_SERVICE_ROLE_KEY` | Scripts (writes only) | Secret — never in backend/frontend |
| `GEMINI_API_KEY` | `llm.py` | Google AI Studio |
| `GEMINI_MODEL` | `llm.py` | Default `gemini-2.5-flash` |
| `OPENROUTER_API_KEY` | `llm.py` | Optional; switches LLM provider |
| `OPENROUTER_MODEL` | `llm.py` | Optional; default `google/gemini-2.5-flash` |
| `X_BEARER_TOKEN` | `scrape_tweets.py` | X API v2 app-only bearer token |
| `X_MAX_PAGES` | `scrape_tweets.py` | Default 3; set 10 in prod |
| `TWSCRAPE_ACCOUNTS` | `scrape_tweets.py` [v4 TODO] | JSON array of X account creds |
| `REDDIT_CLIENT_ID` | `scrape_reddit.py` | Blocked on T-11 |
| `REDDIT_CLIENT_SECRET` | `scrape_reddit.py` | Blocked on T-11 |
| `REDDIT_USER_AGENT` | `scrape_reddit.py` | Blocked on T-11 |
| `TELEGRAM_SESSION` | `scrape_telegram.py` [v4 TODO] | Serialised Telethon session string |
| `PORT` | Backend | 3000 locally; 8080 on Fly.io |
| `FRONTEND_ORIGIN` | Backend | CORS allowed origin; omit for permissive in dev |
| `RUST_LOG` | Backend | e.g. `info` or `oru_kural_backend=debug` |
| `API_BASE_URL` | Frontend (compile-time) | Baked into WASM at `dx build` time |

---

## Deployment

| Service | Platform | Config |
|---|---|---|
| Backend | Fly.io (`oru-kural-backend.fly.dev`) | `fly.toml`, `Dockerfile` |
| Frontend | Vercel (Hobby) | `vercel.json` |
| Database | Supabase free tier | Managed |
| CI/CD | GitHub Actions | `.github/workflows/` |

Build commands:
```bash
# Frontend production build
API_BASE_URL=https://oru-kural-backend.fly.dev dx build --release

# Backend deploy
fly deploy
```

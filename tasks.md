# Oru Kural — Task Tracker

**Progress: 22 / 23 tasks complete.**
One task blocked on external credentials (T-11).

Tasks are ordered by priority. Each is self-contained and executable independently unless a dependency is noted.

---

## HIGH — Blocks production or causes visible breakage

### ~~T-01 · Fix dark mode badge colors~~ — DONE
Badges already use named CSS classes (`badge-demand`, `badge-status-open`, etc.) instead of inline hex styles. `input.css` already has `[data-theme="dark"]` overrides for all 9 category variants and 4 status variants.

---

### ~~T-02 · Add rate limiting to the backend~~ — DONE
Added `tower_governor` middleware: 1 req/sec sustained, burst of 20 per IP. Returns 429 automatically.

---

### ~~T-03 · Add backend test suite~~ — DONE
6 `#[cfg(test)]` tests added — deserialization of all four model types + serialization of `PagedResponse` and `HealthResponse`.

---

### ~~T-04 · Add frontend API retry with exponential backoff~~ — DONE
`with_retry` helper added in `api.rs` — retries up to 3× with 0 / 300 / 600 ms backoff using `gloo_timers`.

---

### ~~T-05 · Surface API errors as user-visible messages~~ — DONE
`error: Signal<Option<String>>` added to each tab component. On failure a clickable inline banner appears with retry.

---

### ~~T-06 · Fix CORS permissive fallback~~ — CLOSED (not an issue)
The permissive fallback is intentional for local dev. Production always has `FRONTEND_ORIGIN` set (Fly.io env var), so the fallback never runs in production. Hardcoding `localhost:8080` breaks dev because browsers treat `localhost` and `127.0.0.1` as different origins and `dx serve` can run on varying ports.

---

## MEDIUM — Operational and correctness issues

### ~~T-07 · Replace `eprintln!` with structured logging in backend~~ — DONE
Added `tracing` + `tracing-subscriber` (JSON format, `RUST_LOG`-controlled) to `Cargo.toml`. Initialized JSON subscriber in `main.rs`. Replaced all `eprintln!` in `handlers.rs` with `tracing::error!` / `tracing::warn!`. `TraceLayer` logs method, URI, and request ID per request.

---

### ~~T-08 · Fix GitHub Actions workflow — remove legacy categorize step~~ — DONE
Deleted the `categorize_tweets.py` step from `weekly_scrape.yml`. Step renamed to reflect v3 pipeline clearly.

---

### ~~T-09 · Implement issue search on the backend~~ — DONE
Added `search_query: Option<String>` to `IssuesQuery`. `list_issues()` passes `?or=(title.ilike.*{q}*,summary.ilike.*{q}*)` to Supabase when present. Frontend: `fetch_issues` takes `search_query` arg; `filter_bar.rs` debounces 300 ms (version-counter + `gloo_timers::future::sleep`) before updating the parent signal; `issues_board.rs` subscribes to `search_query` in its effect and passes it to all `fetch_issues` call sites (initial, retry, load-more). Client-side filtering removed.

---

### ~~T-10 · Add input validation for query parameters~~ — DONE
`limit` clamped with `.clamp(1, MAX_LIMIT)` (min 1, max 100) in all three handlers. Invalid base64 cursors already return `400 Bad Request` via `B64.decode()` failure path.

---

### T-11 · Wire up Reddit OAuth (PRAW)
**Area:** `scripts/scrape_reddit.py`
Currently uses the unauthenticated JSON fallback (`reddit.com/{subreddit}.json`). This is rate-limited to ~30 requests/10 min and subject to removal.

**What to do:**
- Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` to `.env.example` (with blank values).
- In `scrape_reddit.py`, check for these vars at startup; if present, use PRAW OAuth. If absent, fall back to current JSON path with a warning.
- Add the three new secrets to the GitHub Actions workflow file (blank, to be filled when approved).

---

### ~~T-12 · Add request timeout enforcement in the backend~~ — DONE
Introduced `fetch_json<T>` helper in `handlers.rs` that wraps each Supabase send+json call in `tokio::time::timeout(10s)`. Returns `504 Gateway Timeout` on deadline exceeded. All handlers (list_issues, get_issue×3, list_signals, list_events, get_stats) use the helper.

---

## LOW — Quality of life improvements

### ~~T-13 · Add response compression middleware~~ — DONE
Added `tower-http` `CompressionLayer` (gzip + brotli) to the Axum middleware stack in `main.rs`.

---

### ~~T-14 · Add request ID header for log correlation~~ — DONE
`SetRequestIdLayer` (UUID v4) assigns `x-request-id` on every incoming request. `PropagateRequestIdLayer` copies it to the response. `TraceLayer` creates a span per request with `request_id` as a field — all `tracing::error!` calls in handlers are children of that span and carry the ID in structured JSON output.

---

### ~~T-15 · Add accessibility labels to interactive elements~~ — DONE
Added `aria-label` to: dark mode toggle, tab nav buttons, issue detail close button, load-more pagination buttons (`issues_board.rs`, `events_feed.rs`), all filter pill buttons (`filter_bar.rs`).

---

### ~~T-16 · Add loading skeleton for initial issues fetch~~ — DONE (was already correct)
`loading` signal initialises to `true`; 6 skeleton cards render immediately on first load before the API response arrives.

---

### ~~T-17 · Add per-step timeout to GitHub Actions workflow~~ — DONE
Added `timeout-minutes: 10` to every script step in `weekly_scrape.yml`.

---

### ~~T-18 · Add a health/readiness check to the Fly.io deployment~~ — DONE
Added `[checks.health]` block to `fly.toml` — `GET /health` on port 8080, 10 s interval, 5 s grace period, 2 s timeout.

---

### ~~T-19 · Deduplicate signal_issue_map on pipeline re-runs~~ — DONE
Migration `009` adds `UNIQUE INDEX` on `(signal_id, issue_id)`. `link_signals()` in `cluster_issues.py` now passes `?on_conflict=signal_id,issue_id` to PostgREST.

---

### ~~T-20 · Add Fly.io deploy step to GitHub Actions~~ — DONE
Created `.github/workflows/deploy_backend.yml` — triggers on push to `main` when `backend/**` or `fly.toml` changes. Requires `FLY_API_TOKEN` secret.

---

## Pipeline enhancements

### ~~T-21 · Add incremental clustering (only re-cluster new signals)~~ — DONE
`cluster_issues.py` queries the last completed `cluster_issues` run's `completed_at` and adds `scraped_at=gte.<timestamp>` to the Supabase query. Falls back to full fetch on first run.

---

### ~~T-22 · Add signal deduplication before categorization~~ — DONE
`categorize_signals.py` computes Jaccard similarity across the uncategorized batch. Signals above 0.85 threshold are patched with `duplicate_of` and excluded from Gemini. Migration `009` adds `duplicate_of` column + index to `signals` table. `fetch_uncategorized_signals` now filters `duplicate_of=is.null`.

---

### ~~T-23 · Add scrape_runs failure alerting~~ — DONE
`scrape_tweets.py` and `scrape_reddit.py` call `sys.exit(1)` when 0 rows are upserted on a live run. Reddit step in `weekly_scrape.yml` has `continue-on-error: true` (403 from unauthenticated API is expected until PRAW is approved).

---

## Remaining open tasks at a glance

| ID | Area | Summary |
|---|---|---|
| T-11 | Scripts | Reddit PRAW OAuth — blocked pending Reddit API credentials |

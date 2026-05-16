# Oru Kural — Future Tasks

Ordered by priority. Each task is self-contained and executable independently unless a dependency is noted.

---

## HIGH — Blocks production or causes visible breakage

### T-01 · Fix dark mode badge colors
**Area:** `frontend/input.css`, `frontend/src/components/`
Status and category badge colors use inline `style=` with light-mode hex values in `category_badge.rs` and `status_badge.rs`. The `[data-theme="dark"]` block in `input.css` defines background/surface/text overrides but there are no dark equivalents for badge colors. In dark mode, badges render light-mode colors against a dark background.

**What to do:**
- Define `--color-tvk-status-*` and `--color-tvk-category-*` CSS variables in the `@theme` block for both light and dark.
- Replace hardcoded hex values in `category_color()` and `status_color()` with `var(--color-tvk-category-*)` references.
- Verify all 9 categories and 4 statuses look correct in both themes.

---

### T-02 · Add rate limiting to the backend
**Area:** `backend/src/main.rs`, `backend/Cargo.toml`
The backend has no rate limiting. Any client can hammer `/issues`, `/signals`, or `/stats` without restriction. The Supabase free tier has request limits; sustained abuse will exhaust the quota.

**What to do:**
- Add `tower_governor` (or `tower-http`'s `RateLimit`) as a middleware layer in `main.rs`.
- Apply a per-IP limit (e.g., 60 req/min) across all routes.
- Return `429 Too Many Requests` with a `Retry-After` header.

---

### T-03 · Add backend test suite
**Area:** `backend/src/`, `backend/tests/`
Zero tests. Any change to handler deserialization or query building is unverifiable without running the full stack.

**What to do:**
- Add `#[cfg(test)]` modules in `handlers.rs` with unit tests for query parameter parsing and cursor encoding/decoding.
- Add integration tests in `backend/tests/` that deserialize fixture JSON (captured Supabase REST responses) into `Signal`, `Issue`, `CmEvent`, and `CategoryStat` structs.
- Add at least one compile-time test that the `AppState` type implements `Clone`.

---

### T-04 · Add frontend API retry with exponential backoff
**Area:** `frontend/src/api.rs`
All five fetch functions (`fetch_issues`, `fetch_issue_detail`, `fetch_events`, `fetch_stats`) send a single HTTP request with no retry. A transient Fly.io cold start or network hiccup fails silently with an empty state.

**What to do:**
- Extract a `fetch_with_retry(url, max_attempts=3, base_delay_ms=300)` helper.
- Replace all `.send().await` call sites with the helper.
- Cap attempts at 3; use jittered exponential backoff (300ms, 600ms, 1200ms).

---

### T-05 · Surface API errors as user-visible messages
**Area:** `frontend/src/components/issues_board.rs`, `events_feed.rs`, `stats_panel.rs`, `api.rs`
API failures currently only call `eprintln!`. Users see a blank panel with no indication that something went wrong.

**What to do:**
- Add an `error: Signal<Option<String>>` to each tab component.
- When a fetch returns `Err`, set the error signal instead of (or in addition to) logging.
- Render an inline error banner ("Could not load issues — tap to retry") above the empty state.
- Clear the error signal on a successful subsequent fetch.

---

### T-06 · Fix CORS permissive fallback
**Area:** `backend/src/main.rs`
When `FRONTEND_ORIGIN` is unset, the backend allows any origin. This is fine locally but dangerous if the backend URL is ever shared publicly before the env var is set in production.

**What to do:**
- Change the fallback from permissive-any to a hard `http://localhost:8080` (the only legitimate local origin).
- Document in `.env.example` that `FRONTEND_ORIGIN` must be set in all deployed environments.

---

## MEDIUM — Operational and correctness issues

### T-07 · Replace `eprintln!` with structured logging in backend
**Area:** `backend/src/handlers.rs`, `backend/src/main.rs`, `backend/Cargo.toml`
All logging uses `eprintln!`. Fly.io can stream structured JSON logs but there is nothing to stream.

**What to do:**
- Add `tracing` + `tracing-subscriber` to `Cargo.toml`.
- Initialize a JSON-format subscriber in `main.rs` (env-controlled log level via `RUST_LOG`).
- Replace every `eprintln!` in handlers with `tracing::error!` / `tracing::warn!` / `tracing::info!`.
- Add `tracing::info!` at request entry for each handler (method, path, query params).

---

### T-08 · Fix GitHub Actions workflow — remove legacy categorize step
**Area:** `.github/workflows/weekly_scrape.yml`
Step 2 still runs `categorize_tweets.py` (v2 legacy) immediately after scraping tweets. Step 5 runs `categorize_signals.py` (v3 active). This means v2 categorization runs redundantly, wasting Gemini quota and potentially overwriting v3 state.

**What to do:**
- Delete or comment out the `categorize_tweets.py` step from the workflow.
- Rename the step header to reflect the v3 pipeline clearly.
- Update the step ordering comments.

---

### T-09 · Implement issue search on the backend
**Area:** `backend/src/handlers.rs`
`IssuesQuery` accepts a `search_query: Option<String>` parameter but the handler never passes it to Supabase. The filter bar's search box on the Issues tab has no effect.

**What to do:**
- Add an `ilike` filter on `title` and `summary` columns when `search_query` is present in `list_issues()`.
- Use Supabase PostgREST's `ilike` or `or` operator format: `?or=(title.ilike.*{q}*,summary.ilike.*{q}*)`.
- Add a debounce (300ms) to the search input in `filter_bar.rs` before triggering the fetch.

---

### T-10 · Add input validation for query parameters
**Area:** `backend/src/handlers.rs`
`limit` in `IssuesQuery`, `SignalsQuery`, and `EventsQuery` is unbounded. A request with `limit=100000` will ask Supabase for 100k rows.

**What to do:**
- Clamp `limit` to a max of 100 and a min of 1 in each handler before building the Supabase URL.
- Return `400 Bad Request` if `cursor` contains characters outside base64-url alphabet.

---

### T-11 · Wire up Reddit OAuth (PRAW)
**Area:** `scripts/scrape_reddit.py`
Currently uses the unauthenticated JSON fallback (`reddit.com/{subreddit}.json`). This is rate-limited to ~30 requests/10 min and subject to removal.

**What to do:**
- Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` to `.env.example` (with blank values).
- In `scrape_reddit.py`, check for these vars at startup; if present, use PRAW OAuth. If absent, fall back to current JSON path with a warning.
- Add the three new secrets to the GitHub Actions workflow file (blank, to be filled when approved).

---

### T-12 · Add request timeout enforcement in the backend
**Area:** `backend/src/main.rs`, `backend/src/handlers.rs`
There is no request-level timeout. A slow Supabase response will hold the Tokio thread indefinitely.

**What to do:**
- Wrap each Supabase `reqwest` call with `tokio::time::timeout(Duration::from_secs(10), ...)`.
- Return `504 Gateway Timeout` if the upstream call exceeds the deadline.

---

## LOW — Quality of life improvements

### T-13 · Add response compression middleware
**Area:** `backend/src/main.rs`, `backend/Cargo.toml`
Backend responses are uncompressed JSON. The `/issues` and `/signals` responses can be 20–60KB on a full page.

**What to do:**
- Add `tower-http`'s `CompressionLayer` (gzip + brotli) to the middleware stack.
- No changes needed in frontend (browsers auto-decompress).

---

### T-14 · Add request ID header for log correlation
**Area:** `backend/src/main.rs`
Without request IDs there is no way to correlate a frontend error with a specific backend log line.

**What to do:**
- Add `tower-http`'s `SetRequestIdLayer` / `PropagateRequestIdLayer`.
- Log the request ID in every `tracing::error!` in handlers (depends on T-07).
- Return the request ID in an `X-Request-Id` response header so the frontend can log it.

---

### T-15 · Add accessibility labels to interactive elements
**Area:** `frontend/src/components/`
Buttons use emoji or Tamil text without `aria-label` attributes. Screen readers will read emoji names literally ("WHITE HEAVY CHECK MARK", etc.).

**What to do:**
- Add `aria_label` attributes to: dark mode toggle button (`header.rs`), issue detail close button (`issue_detail.rs`), pagination load-more buttons (`issues_board.rs`, `events_feed.rs`), filter pill buttons (`filter_bar.rs`).

---

### T-16 · Add loading skeleton for initial issues fetch
**Area:** `frontend/src/components/issues_board.rs`
The skeleton cards (`skeleton_card.rs`) exist but are only shown during subsequent loads. The very first page load shows a blank board until the API response arrives.

**What to do:**
- Initialize `issues: Signal<Vec<Issue>>` to trigger a skeleton render immediately.
- Show 6 skeleton cards whenever `loading` is true AND `issues` is empty (first load).

---

### T-17 · Add per-step timeout to GitHub Actions workflow
**Area:** `.github/workflows/weekly_scrape.yml`
The workflow has a 45-minute job timeout but no per-step timeout. A hung Gemini call in `cluster_issues.py` can block all subsequent steps silently.

**What to do:**
- Add `timeout-minutes: 10` to each script step.
- Add `continue-on-error: false` explicitly where a failure should abort the run.

---

### T-18 · Add a health/readiness check to the Fly.io deployment
**Area:** `fly.toml` (if it exists) or deployment config
The `/health` endpoint exists but may not be wired into Fly.io's health check configuration.

**What to do:**
- Confirm `fly.toml` has a `[checks]` section pointing to `GET /health`.
- Set an appropriate interval (10s) and grace period (5s).

---

### T-19 · Deduplicate signal_issue_map on pipeline re-runs
**Area:** `scripts/cluster_issues.py`, `scripts/link_events_to_issues.py`
Re-running the clustering pipeline may insert duplicate rows in `signal_issue_map` if the upsert logic doesn't cover composite key conflicts.

**What to do:**
- Verify the Supabase upsert in `cluster_issues.py` uses `on_conflict=(signal_id, issue_id)`.
- Add a uniqueness constraint in a new migration if not already present.

---

### T-20 · Add Fly.io deploy step to GitHub Actions (optional)
**Area:** `.github/workflows/`
The data pipeline runs weekly but the backend is deployed manually. A separate workflow triggered on push to `main` would automate this.

**What to do:**
- Create `.github/workflows/deploy_backend.yml` triggered on push to `main` (path filter: `backend/**`).
- Use `superfly/flyctl-actions` + `FLY_API_TOKEN` secret to run `flyctl deploy --remote-only`.

---

## Pipeline enhancements

### T-21 · Add incremental clustering (only re-cluster new signals)
**Area:** `scripts/cluster_issues.py`
Currently re-clusters all signals every run. As the dataset grows, this wastes Gemini tokens on signals already assigned to issues.

**What to do:**
- Track a `last_clustered_at` timestamp in `scrape_runs`.
- Pass a `created_at > last_clustered_at` filter to the Supabase query at the start of `cluster_issues.py`.
- Only submit unclustered signals to Gemini; merge results into existing issues where semantically similar.

---

### T-22 · Add signal deduplication before categorization
**Area:** `scripts/categorize_signals.py`
Near-duplicate tweets (quote-tweets, copy-paste complaints) are categorized as separate signals and inflating issue voice counts.

**What to do:**
- After fetching uncategorized signals, compute cosine similarity (or a simple Jaccard over word sets) between new signals and recent signals in the same category.
- Flag signals above a similarity threshold (e.g., 0.85) as `duplicate` and skip Gemini categorization for them.
- Store the `duplicate_of` signal ID in the `signals` table (requires a new column / migration).

---

### T-23 · Add scrape_runs failure alerting
**Area:** `.github/workflows/weekly_scrape.yml`, `scripts/`
Workflow failures send a GitHub notification, but partial failures (e.g., X API rate-limited, 0 tweets scraped) are logged as success because the script exits 0.

**What to do:**
- Have each scrape script exit with code 1 if 0 rows were upserted AND the run was not a dry-run.
- Set `continue-on-error: true` only on the Reddit step (fallback is expected to degrade gracefully).

---

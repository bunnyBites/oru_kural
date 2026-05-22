# Oru Kural — v4 Technical Approach

This document records the key design decisions for the v4 multi-source release.
Read alongside `roadmap.md` (what) and `structure.md` (where).

---

## Signal source architecture

The `signals` table already has a `source TEXT` column and a `score INT` column.
Adding new sources is zero-schema-change for the pipeline — each scraper sets its own `source` value
and the rest of the pipeline (categorize → cluster → link) treats all sources identically.

| source value | Scraper | Signal type |
|---|---|---|
| `x` | `scrape_tweets.py` | Citizen posts mentioning @CMOTamilnadu |
| `reddit` | `scrape_reddit.py` | Posts from r/Chennai, r/TamilNadu |
| `cm_helpline` | `scrape_grievances.py` | Synthetic — aggregate grievance category count |
| `gcc_pgr` | `scrape_grievances.py` | Synthetic — Chennai GCC grievance count |
| `telegram` | `scrape_telegram.py` (TODO) | Public district channel posts |

Instagram is **not** a signal source — the CMO page has no public complaint mentions. Instagram data
goes into `cm_events` only.

---

## twscrape over X API v2

Decision: replace `scrape_tweets.py`'s REST calls with `twscrape`.

| Dimension | X API v2 | twscrape |
|---|---|---|
| Cost | ~$100/month | Free |
| Auth | Bearer token (app-level) | Real account credentials |
| Rate limits | 10,000 tweets/month (Basic) | Browser-level — ~100/week is trivial |
| Reliability | Stable API contract | May break on X UI changes |
| Ban risk | None | Low at weekly cadence with 2–3 accounts |

`scrape_tweets.py` output is unchanged — same row shape, same `source="x"`, same
`has_engagement()` filter. The only change is how tweets are fetched.

**Account storage:** `TWSCRAPE_ACCOUNTS` GitHub secret = JSON array:
```json
[{"username":"...", "password":"...", "email":"...", "email_password":"..."}]
```

**Session file:** `twscrape` writes a SQLite session DB. For GitHub Actions, serialize it to/from
a GitHub Actions cache keyed on a weekly hash so accounts re-login at most once per week.

---

## Synthetic signals (CM Helpline / GCC PGR)

Individual grievances from `cmhelpline.tnega.org` are login-gated — we cannot scrape them.
The public landing page exposes aggregate category counts (e.g. "Road: 342 pending").

Strategy: convert each count to one synthetic signal row:
```
content = "CM Helpline grievance category 'Road': 342 pending petitions as of 2026-05-19."
source  = "cm_helpline"
category = "Complaint"      ← pre-set, confidence 1.0 → bypasses Gemini batch
```

This feeds the existing clustering pipeline without any code changes downstream.
Deduplication: `external_id = "helpline_{date}_{category[:40]}"` — one row per category per day.

---

## Tamil content generation

**Why not translate at scrape time:** signals arrive in both Tamil and English. Translating every signal
is expensive and not always useful — most signals get filtered out before clustering.

**Where translation happens:** `cluster_issues.py`, after a new issue is created. The Tamil pass is
a second Gemini call per batch of 20 new issues:
```
For each issue title + summary, produce:
  title_ta: Tamil translation ≤ 12 words
  summary_ta: 1–2 sentence Tamil synthesis of the citizen demand
```

**Schema:** migration 010 adds `title_ta TEXT` and `summary_ta TEXT` to the `issues` table.
Both nullable — frontend falls back to English when null (before back-fill or on Gemini failures).

**Back-fill:** on first run after migration 010, `cluster_issues.py` queries `title_ta IS NULL` for
existing issues and runs the Tamil pass over them in batches of 20.

---

## Frontend Tamil toggle

`AppCtx` (in `app_shell.rs`) adds `tamil_mode: Signal<bool>` alongside `dark_mode`.

Each component that renders issue/signal text checks `tamil_mode` before picking the field:
```rust
let title = if tamil_mode() && issue.title_ta.is_some() {
    issue.title_ta.as_deref().unwrap()
} else {
    &issue.title
};
```

The toggle is a button in `header.rs`, same pattern as the dark-mode toggle. State persists in
`localStorage` via `document::eval()`. No new API calls — all fields are already in the response.

---

## LLM abstraction

All Gemini calls go through `scripts/llm.py`. The callers (`categorize_signals.py`,
`cluster_issues.py`, `scrape_cm_events.py`, `link_events_to_issues.py`) never import
`google-genai` directly.

`llm.py` reads:
- `GEMINI_API_KEY` + `GEMINI_MODEL` (default `gemini-2.5-flash`) → direct Google AI Studio path
- `OPENROUTER_API_KEY` (presence switches the whole module to OpenRouter) + `OPENROUTER_MODEL`

This means the entire pipeline can switch providers by adding one env var — useful for
cost comparison or rate-limit fallback.

---

## Supabase key split

| Consumer | Key | Reason |
|---|---|---|
| Python scripts (writes) | `SUPABASE_SERVICE_ROLE_KEY` | Bypasses RLS for INSERT/UPSERT |
| Python scripts (reads) | `SUPABASE_ANON_KEY` | Validates RLS policies |
| Axum backend | `SUPABASE_ANON_KEY` | Read-only proxy — never needs write access |
| Frontend (WASM) | No key | All reads through Axum backend |

Service role key must never appear in `backend/` or `frontend/` source.

---

## Port split (local dev)

| Service | Port | Why |
|---|---|---|
| Axum backend | 3000 | Set via `PORT=3000` in `.env` |
| Dioxus dev server | 8080 | `dx serve` default |

Do not run the backend on 8080 locally — `dx serve` occupies it and the frontend
receives HTML instead of JSON from the API.

In production (Fly.io) the backend runs on 8080. `API_BASE_URL` is baked into the WASM
binary at `dx build --release` time via `option_env!("API_BASE_URL")`.

---

## Pagination

All list endpoints use keyset pagination — no `OFFSET`, no `COUNT(*)`.
Cursor = base64-encoded `posted_at` timestamp (or `last_updated_at` for issues).
Next page token is `null` when fewer rows than `limit` are returned.
`limit` is clamped server-side: min 1, max 100.

---

## Rate limiting

`tower_governor` in the Axum middleware stack: 1 req/sec sustained, burst of 20 per IP.
Returns 429 automatically. Not configurable per route — applies globally.

---

## Error handling conventions

**Python scripts:**
- Never bare `except` — always `except Exception as e`.
- Gemini API errors: exponential backoff with jitter, base=2, cap=60s, max 4 retries (in `llm.py`).
- Gemini JSON parse failure: log raw response, insert `categorization_failures` row, skip batch, continue run.
- 0 upserted on a live run (`scrape_tweets.py`, `scrape_reddit.py`): `sys.exit(1)` to fail the workflow step.
- `scrape_grievances.py` uses `continue-on-error: true` in the workflow — portal markup changes are expected.

**Axum backend:**
- Supabase calls wrapped in `fetch_json<T>` with 10s timeout → 504 on breach.
- Deserialization errors propagate as 500.
- All paths return structured JSON (never HTML error pages).

# Oru Kural — v4 Roadmap

Branch: `feature/v4-multi-source`
Goal: drop scraping costs to near-zero, add new civic signal sources, ship Tamil UI.

---

## Three pillars

| Pillar | Why |
|---|---|
| Cost | X API v2 costs ~$100/month for ~100 tweets/week — 93 % of total running cost |
| Sources | X + Reddit alone miss PG Portal grievances, Telegram district channels, Instagram CMO posts |
| Tamil UI | Dashboard content is about Tamil Nadu civic issues — Tamil readers should get Tamil output |

---

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Replace X API v2 with `twscrape` in `scrape_tweets.py` | TODO |
| M2 | `scrape_grievances.py` — CM Helpline + GCC PGR stats as synthetic signals | **Done** |
| M3 | `scrape_instagram.py` — CMO Instagram → `cm_events` table | TODO |
| M4 | `scrape_telegram.py` — public district Telegram channels → `signals` table | TODO |
| M5 | Migration 010 — `title_ta`, `summary_ta` columns on `issues` | TODO |
| M6 | Update `cluster_issues.py` — Gemini Tamil generation pass | TODO |
| M7 | Frontend Tamil/English toggle | TODO |
| M8 | GitHub Actions workflow updates for new scripts | Partial |
| M9 | Custom domain setup | TODO |

---

## M1 — twscrape migration

**What changes:** `scrape_tweets.py` stops calling the X API v2 REST endpoint and instead drives
`twscrape` (authenticated web scraping via real X accounts stored as GitHub secrets).

**Why twscrape over alternatives:**
- Apify: tried and rejected — unreliable responses, still costs money.
- Nitter: shut down; mirrors are unstable.
- twscrape: active community, drop-in async interface, free for ≤ 100 tweets/week at weekly cadence.

**Account risk:** weekly scrape of ~100 tweets with dormant accounts = low ban exposure. Use 2–3 throwaway
accounts spread across requests.

**GitHub secrets required:** `TWSCRAPE_ACCOUNTS` (JSON array of `{username, password, email, email_password}`).

**Interface stays the same:** output rows identical to current `scrape_tweets.py` — same Supabase upsert,
same `source="x"` value, same `has_engagement()` filter.

---

## M2 — CM Helpline + GCC PGR (Done)

`scrape_grievances.py` scrapes aggregate grievance category counts from:
- `cmhelpline.tnega.org` — official 2026 TVK government helpline (1100 toll-free)
- `gccservices.in/pgr` — Chennai Corporation grievance portal

Each category count becomes a synthetic signal with `source="cm_helpline"` or `source="gcc_pgr"`.
Pre-categorised as `Complaint` (confidence 1.0) so the clustering pipeline surfaces overloaded departments.

---

## M3 — CMO Instagram

**Source:** official CMO Tamil Nadu Instagram page (public).
**Library:** `instaloader` (no API key required for public pages).
**Destination:** `cm_events` table (NOT `signals` — Instagram is for official announcements, not civic complaints).
**Deduplication:** upsert on synthetic `source_url` = `https://instagram.com/p/{shortcode}`.

---

## M4 — Telegram public channels

**Sources:** public district collector channels and TN Gov news channels.
**Library:** `telethon` (no bot token needed for public channels — reader-only MTProto session).
**Destination:** `signals` table with `source="telegram"`.
**Filter:** posts mentioning CM / government policy / civic issues, last 7 days.

---

## M5–M6 — Tamil content

New columns `title_ta` (TEXT) and `summary_ta` (TEXT) on the `issues` table, added in migration 010.

`cluster_issues.py` gets a second Gemini pass that:
1. Takes every `issue` row where `title_ta IS NULL`.
2. Calls Gemini with a translate-to-Tamil prompt (batch 20).
3. PATCHes back `title_ta` and `summary_ta`.

Back-fill runs on the first pipeline execution after migration 010 is applied.

---

## M7 — Tamil/English toggle

Location: header, next to the dark-mode toggle.

Affects:
- Issues Board: switches between `title` / `title_ta` and `summary` / `summary_ta`
- Signals (inside issue detail): switches between `translated_content` (English) and `content` (original — may be Tamil)
- Event cards: title/description stay English-only (RSS sources are English)

Implementation: `AppCtx` gains a `tamil_mode: Signal<bool>` field. Components read it via `use_context()`.
No network calls — all data already in the response payload.

---

## M8 — Workflow updates

`weekly_scrape.yml` changes needed when milestones are done:
- Replace `scrape_tweets.py` step env vars (`X_BEARER_TOKEN` → `TWSCRAPE_ACCOUNTS`)
- Add `scrape_instagram.py` step after `scrape_cm_events.py` (same env pattern)
- Add `scrape_telegram.py` step (add `TELEGRAM_SESSION` secret)

`scrape_grievances.py` step is already in the workflow (M2 done).

---

## M9 — Custom domain

Two options:
1. **Subdomain of existing Bluehost domain** — add a CNAME record in Bluehost pointing to `cname.vercel-dns.com`. Zero cost.
2. **New `orukural.in`** — register on Cloudflare Registrar (~₹270/year, cheapest TLD option).

Vercel side: Settings → Domains → add domain → copy the CNAME value shown.

---

## Cost after v4

| Item | Before | After |
|---|---|---|
| X API v2 | ~$100/month | $0 (twscrape) |
| Gemini Flash (categorize + cluster + link) | ~$2–4/month | ~$2–4/month (unchanged) |
| Supabase free tier | $0 | $0 |
| Fly.io Machines (backend) | ~$3/month | ~$3/month |
| Vercel Hobby (frontend) | $0 | $0 |
| **Total** | **~$105/month** | **~$5–7/month** |

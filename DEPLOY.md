# Oru Kural — Deployment Guide

Complete these steps in order for a fresh deployment.

---

## 1. Prerequisites

```bash
# Fly.io CLI
curl -L https://fly.io/install.sh | sh && fly auth login

# Vercel CLI
npm i -g vercel && vercel login

# Dioxus CLI
cargo install dioxus-cli

# Rust (for backend)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

---

## 2. Supabase — Run Migrations

Open your Supabase project → **SQL Editor** and run each file below **in order**:

| Order | File | What it does |
|---|---|---|
| 1 | `supabase/migrations/002_scale_indexes_and_scrape_runs.sql` | Indexes + scrape_runs table |
| 2 | `supabase/migrations/003_category_stats.sql` | category_stats table |
| 3 | `supabase/migrations/004_retention_archive.sql` | Archival/retention rules |
| 4 | `supabase/migrations/005_categorization_failures.sql` | Failure tracking |
| 5 | `supabase/migrations/006_v3_schema.sql` | issues, cm_events, signal_issue_map |
| 6 | `supabase/migrations/007_signals_table.sql` | signals table (replaces tweets) |
| 7 | `supabase/migrations/008_anon_read_policies.sql` | RLS policies — **required** for backend reads |
| 8 | `supabase/migrations/009_dedup_and_duplicate_of.sql` | Dedup index + duplicate_of column |
| 9 | `supabase/migrations/010_tamil_columns.sql` | title_ta, summary_ta on issues |
| 10 | `supabase/migrations/011_scrape_runs_anon_read.sql` | RLS for scrape_runs — required for /meta |

> **Important:** Migration 008 is required. Without it the anon key returns empty arrays from all tables.

---

## 3. Fly.io — Deploy the Axum Backend

```bash
# From the project root (first time only):
fly launch --no-deploy

# Set secrets:
fly secrets set \
  SUPABASE_URL="https://<project-ref>.supabase.co" \
  SUPABASE_ANON_KEY="your_anon_key" \
  FRONTEND_ORIGIN="https://oru-kural.vercel.app"

# Deploy:
fly deploy

# Verify:
fly status
curl https://oru-kural-backend.fly.dev/health
curl https://oru-kural-backend.fly.dev/meta
```

> Backend URL will be `https://oru-kural-backend.fly.dev` — you need this for the frontend build.

---

## 4. Vercel — Deploy the Frontend

The frontend is a Dioxus WASM app. `API_BASE_URL` is **baked in at compile time** — use `build_web.sh`:

```bash
# From the project root:
API_BASE_URL=https://oru-kural-backend.fly.dev ./build_web.sh
```

This script:
1. Compiles the WASM with the backend URL embedded
2. Injects the SPA rewrite `vercel.json` into the output directory
3. Runs `vercel <output-dir> --prod` automatically

During the first `vercel` run you'll be prompted to link the project — follow the prompts.

**Stable production URL:** `https://oru-kural.vercel.app`

> **Do NOT run `vercel --prod` from the repo root** — it deploys an empty shell with no WASM. Always use `build_web.sh`.

---

## 5. GitHub Actions — Add Secrets

Go to your GitHub repo → **Settings → Secrets and variables → Actions** and add:

| Secret | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Project Settings → API |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → API Keys |
| `X_BEARER_TOKEN` | [console.x.com](https://console.x.com) → your app → Keys and tokens |
| `FLY_API_TOKEN` | [fly.io](https://fly.io) dashboard → Access Tokens |
| `ALERT_EMAIL_USER` | Gmail address that sends failure alerts |
| `ALERT_EMAIL_PASSWORD` | Gmail App Password — myaccount.google.com → Security → App Passwords |
| `ALERT_EMAIL_TO` | Recipient address for pipeline failure emails |

Test the pipeline: **Actions → Twice-Weekly Scraper → Run workflow**

---

## 6. Seed initial data

The Issues Board is empty until the full pipeline has run at least once:

```bash
cd scripts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scrape_tweets.py
python scrape_reddit.py
python scrape_cm_events.py
python scrape_grievances.py
python categorize_signals.py
python cluster_issues.py
python link_events_to_issues.py
```

After this the dashboard will show real data. Subsequent runs are automated (Mon + Thu, 2am UTC).

---

## 7. Cost reference

| Service | Cost | Billing |
|---|---|---|
| Supabase | Free | — |
| Vercel (Hobby) | Free | — |
| Fly.io | ~$3/month | fly.io → Billing |
| Google Gemini Flash | ~$2–4/month | aistudio.google.com → Billing |
| X API v2 | ~$1–2/month | developer.x.com → Billing (pre-pay $10–15) |
| **Total** | **~$6–9/month** | |

---

## Re-deploying after code changes

```bash
# Backend only:
fly deploy

# Frontend only:
API_BASE_URL=https://oru-kural-backend.fly.dev ./build_web.sh

# Both (backend auto-deploys via GitHub Actions on push to main):
git push origin main
```

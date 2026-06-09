# Oru Kural — Operations Runbook

This document is for the team that **operates** Oru Kural day-to-day.  
You do not need to write code or understand Rust/Python to follow these procedures.

---

## System overview

```
Data sources         Pipeline (GitHub Actions)      Database        Dashboard
─────────────        ─────────────────────────      ────────        ─────────
X (@CMOTamilnadu) ─┐                                            ┌─ Vercel → orukural.in
Reddit            ─┼─► Runs Mon + Thu, 2am UTC ──► Supabase ──►┤
TN Gov RSS        ─┤   (fully automated)                        └─ Fly.io → oru-kural-backend.fly.dev
CM Helpline stats ─┘
```

**Live URLs:**
- Dashboard: https://orukural.in
- Backend API: https://oru-kural-backend.fly.dev
- Health check: https://oru-kural-backend.fly.dev/health
- Last scrape info: https://oru-kural-backend.fly.dev/meta

The pipeline runs automatically. Most weeks you will do nothing.  
This runbook tells you what to do when something looks wrong.

---

## Daily checks (optional)

- Open the dashboard and confirm the Issues Board loads with recent data.
- The Stats tab should show non-zero signal counts.
- If the board shows "No issues found" or counts look frozen for more than a week, see **Troubleshooting** below.

---

## How to trigger a manual scrape

Useful after adding new data or when you want to refresh before a deadline.

1. Go to the GitHub repository → **Actions** tab.
2. Click **Twice-Weekly Scraper** in the left sidebar.
3. Click **Run workflow** → **Run workflow** (green button).
4. Watch the steps — all should show green checkmarks within 30 minutes.

---

## How to check if the last scrape succeeded

**Option A — GitHub Actions log (easiest)**
1. GitHub repository → **Actions** tab.
2. Click the most recent **Twice-Weekly Scraper** run.
3. Green = success. Red = one or more steps failed. Click the failed step to read the error.

**Option B — Supabase scrape_runs table**
1. Open [supabase.com](https://supabase.com) → your project → **Table Editor** → `scrape_runs`.
2. Sort by `completed_at` descending.
3. Each row is one pipeline step. Check `status` column: `success` or `error`. The `error_message` column shows the failure reason.

---

## What to do when the dashboard shows no new issues

Issues only appear after the **clustering** step runs (`cluster_issues.py`). Scraping alone is not enough.

1. Trigger a manual scrape (see above) and wait for it to complete.
2. If the clustering step shows green but issues are still missing, check that migration `010` is applied in Supabase (Table Editor → `issues` → confirm `title_ta` column exists).
3. If the `issues` table has rows in Supabase but the dashboard shows none, the RLS policy may be missing — confirm migration `008` has been applied.

---

## How to rotate secrets

All secrets live in two places: **GitHub Actions secrets** (for the pipeline) and **Fly.io secrets** (for the backend API). The Supabase keys and Gemini key are the same value in both places.

### GitHub Actions secrets
1. GitHub repository → **Settings** → **Secrets and variables** → **Actions**.
2. Click the secret name → **Update** → paste new value → **Update secret**.

Secrets used by the pipeline:

| Secret | What it is | Where to get a new one |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | Supabase dashboard → Project Settings → API |
| `SUPABASE_ANON_KEY` | Read-only publishable key | Supabase dashboard → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Write key (secret — never share) | Supabase dashboard → Project Settings → API |
| `GEMINI_API_KEY` | Google AI Studio key | [aistudio.google.com](https://aistudio.google.com) → API Keys |
| `X_BEARER_TOKEN` | X API Bearer Token (~$0.65/month) | [developer.x.com](https://developer.x.com) → your app → Keys and tokens |
| `FLY_API_TOKEN` | Fly.io deploy token | Fly.io dashboard → Access Tokens |
| `ALERT_EMAIL_USER` | Gmail address that sends failure alerts | The Gmail account you set up for alerts |
| `ALERT_EMAIL_PASSWORD` | Gmail App Password (not your login) | myaccount.google.com → Security → App Passwords |
| `ALERT_EMAIL_TO` | Who receives pipeline failure alerts | IT team monitored inbox |

### Fly.io backend secrets
```bash
fly secrets set SUPABASE_URL=... SUPABASE_ANON_KEY=... FRONTEND_ORIGIN=https://your-vercel-url
```
Or update via Fly.io dashboard → your app → **Secrets**.

### Vercel frontend
The only compile-time variable is `API_BASE_URL` (the Fly.io backend URL).  
Change it in Vercel dashboard → your project → **Settings → Environment Variables** → redeploy.

---

## Monthly cost breakdown

| Item | Cost | Paid where |
|---|---|---|
| X API v2 credits | ~$1–2/month | [developer.x.com](https://developer.x.com) → Billing (pre-pay $10–15, lasts 6+ months) |
| Google Gemini Flash | ~$2–4/month | [aistudio.google.com](https://aistudio.google.com) → Billing |
| Fly.io backend | ~$3/month | [fly.io](https://fly.io) → Billing |
| Supabase | $0 (free tier) | — |
| Vercel frontend | $0 (Hobby plan) | — |
| **Total** | **~$6–9/month** | |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard loads but shows 0 issues | `cluster_issues.py` has never run, or RLS is missing | Trigger manual scrape; confirm migration 008 applied |
| Issues haven't changed in > 1 week | Pipeline is failing silently | Check Actions log; look for red steps |
| X scrape step is skipped | `X_BEARER_TOKEN` secret is empty or expired | Regenerate token at developer.x.com; update GitHub secret |
| Reddit step fails with 403 | Unauthenticated JSON API is rate-limited | `continue-on-error: true` is set — pipeline still completes; Reddit signals will resume next run |
| Backend returns 502/503 | Fly.io machine is down or OOM | `fly status` in terminal; `fly restart` if needed |
| Frontend shows "Failed to load" | Backend is down, or `FRONTEND_ORIGIN` CORS mismatch | Check Fly.io app status; verify `FRONTEND_ORIGIN` secret matches the Vercel URL exactly |
| Gemini step fails with quota error | Monthly quota exceeded | Check Google AI Studio billing; upgrade plan or wait for quota reset |

---

## Emergency contacts

| Who | Responsibility |
|---|---|
| **Developer (Mukesh Kumar)** — s.mukeshkr481@gmail.com | All code changes, database schema, new features |
| **Supabase support** — supabase.com/support | Database issues, RLS, quota |
| **Fly.io support** — fly.io/docs | Backend hosting, scaling, crashes |
| **Vercel support** — vercel.com/support | Frontend hosting, domain, build failures |

---

## What you should NOT do

- Do not run Supabase migrations numbered 001–010 again — they are already applied; re-running will corrupt the schema.
- Do not edit `frontend/assets/tailwind.css` — it is a generated file and will be overwritten.
- Do not use the `SUPABASE_SERVICE_ROLE_KEY` in the Vercel frontend environment variables — it is a write key and must stay server-side only.
- Do not delete rows from the `scrape_runs` table — it is the only audit trail for pipeline health.

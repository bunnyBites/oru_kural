# Oru Kural — Deployment Checklist

Complete these steps in order. Each section depends on the previous.

---

## 1. Prerequisites

Install the required CLIs:

```bash
# Fly.io CLI
curl -L https://fly.io/install.sh | sh && fly auth login

# Vercel CLI
npm i -g vercel && vercel login

# Dioxus CLI
cargo install dioxus-cli
```

---

## 2. Supabase — Run Migrations

Open your Supabase project → **SQL Editor** and paste + run each file below **in order**.
Skip any file that doesn't exist.

| Order | File |
|---|---|
| 1 | `supabase/migrations/add_translated_content.sql` |
| 2 | `supabase/migrations/002_scale_indexes_and_scrape_runs.sql` |
| 3 | `supabase/migrations/003_category_stats.sql` |
| 4 | `supabase/migrations/004_retention_archive.sql` |
| 5 | `supabase/migrations/005_categorization_failures.sql` |

> Open each file, copy the SQL inside it, paste into the SQL Editor, and click **Run**.

---

## 3. Fly.io — Deploy the Axum Backend

```bash
# From the project root:
fly launch --no-deploy          # creates the app — do NOT deploy yet

fly secrets set \
  SUPABASE_URL="your_supabase_url_here" \
  SUPABASE_ANON_KEY="your_supabase_anon_key_here"

fly deploy                      # build + deploy with secrets in place
fly status                      # confirm machine is running
fly logs                        # tail logs to verify startup
```

After `fly deploy` succeeds, copy your live URL — it will look like:
```
https://oru-kural-backend.fly.dev
```
You need this for the next step.

---

## 4. Vercel — Deploy the Frontend

Before deploying, update the backend URL in the frontend source:

```
frontend/src/api.rs  →  change BACKEND constant to your Fly.io URL
```

Then build and deploy:

```bash
./build_web.sh       # compiles WASM → frontend/dist/
vercel --prod        # deploy to Vercel production
```

During the `vercel` CLI prompts:
- **Output directory:** `frontend/dist`
- **Framework:** leave blank / none (it's a static WASM build)

---

## 5. GitHub Actions — Add Secrets

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add each of these:

| Secret name | Where to find it |
|---|---|
| `X_BEARER_TOKEN` | X Developer Portal → your app → Keys and tokens |
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Project Settings → API |
| `GEMINI_API_KEY` | Google AI Studio → API keys |

3. Test the workflow: **Actions** tab → **Weekly Tweet Scraper** → **Run workflow**

---

## 6. Cost Reference

| Service | Usage | Monthly cost |
|---|---|---|
| Vercel | Static hosting + CDN | Free |
| Fly.io | Axum server (sleeps when idle) | Free |
| GitHub Actions | ~5 min/week cron | Free |
| Supabase | PostgreSQL + REST API | Free |
| Gemini Flash 2.0 | AI categorization | Free |
| X API v2 | ~1,000 tweets/week | ~$5 |
| **Total** | | **~$5/month** |

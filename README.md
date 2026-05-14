# ஒரு குரல் — Oru Kural

**One Voice** — A civic tech window into what Tamil Nadu citizens are saying to their Chief Minister.

Oru Kural scrapes public tweets mentioning the Tamil Nadu CM's official X handle (@CMOTamilnadu), uses AI to categorize them by topic (infrastructure, health, education, complaints, and more), and surfaces the results in a live dashboard — turning the noise of social media into structured civic signal.

---

## Architecture

```
  X / Twitter
      │
      │  (X API v2 search/recent — Bearer Token)
      ▼
 scrape_tweets.py ──────────────────────────┐
                                            │ upsert (batch 100)
                                            ▼
                                    Supabase (PostgreSQL)
                                     table: tweets
                                            │
                         ┌──────────────────┘
                         │  fetch WHERE category IS NULL
                         ▼
              categorize_tweets.py
                         │  Gemini Flash 2.0
                         │  (batch 40 tweets / call)
                         │
                         └──► update category + confidence
                                            │
                                            ▼
                               Axum REST API  :3000
                               GET /api/tweets[?category=]
                               GET /api/tweets/:id
                               GET /api/stats
                                            │
                                            ▼
                            Dioxus 0.7 Web Dashboard  :8080
                            category pills · tweet grid · detail view
```

---

## Setup

### 1. Clone

```bash
git clone https://github.com/your-handle/oru-kural.git
cd oru-kural
```

### 2. Python environment

```bash
cd scripts
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
# fill in your keys:
#   SUPABASE_URL              — project URL from Supabase dashboard
#   SUPABASE_ANON_KEY         — anon/public key from Supabase dashboard
#   SUPABASE_SERVICE_ROLE_KEY — service role key (writes only; never expose in frontend)
#   GEMINI_API_KEY            — Google AI Studio key
#   X_BEARER_TOKEN            — X API v2 app-only bearer token from developer.x.com
```

### 4. Supabase table

Run this SQL in the Supabase SQL editor:

```sql
create table tweets (
  id            text primary key,
  author_handle text not null,
  author_name   text,
  content       text not null,
  posted_at     timestamptz not null,
  category      text,
  confidence    float4,
  raw_json      jsonb,
  scraped_at    timestamptz not null
);
```

### 5. Run the pipeline

```bash
# Step 1 — scrape via X API v2, upsert to Supabase (requires X_BEARER_TOKEN)
python scrape_tweets.py

# Step 2 — categorize all uncategorized tweets with Gemini
python categorize_tweets.py
```

## Data Fetching

Tweets are fetched via the official **X API v2** (`search/recent` endpoint).

- Auth: App-only Bearer Token
- Query: `@CMOTamilnadu -is:retweet lang:ta,en`
- Pagination: up to 1,000 tweets per run (configurable via `MAX_PAGES`)
- Cost: ~$0.005/tweet — 1,000 tweets/week ≈ $5/month
- Run weekly to stay within the 7-day recency window

A legacy Apify-based scraper is preserved at `scripts/scrape_tweets_apify.py` for one-time historical backfill only.

### Running the scraper
```bash
cd scripts
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in your keys
python scrape_tweets.py
```

### 6. Run the backend

```bash
cd backend
# Add DATABASE_URL and PORT to .env first (see .env.example)
cargo run
# → http://localhost:3000
```

### 7. Run the frontend

```bash
# Terminal A — compile Tailwind (run once, then watch)
cd frontend
npm run css

# Terminal B — serve the Dioxus app
cd frontend
dx serve
# → http://localhost:8080
```

---

## Phase roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **1 — Data pipeline** | ✅ Done | X API v2 scraper → Supabase, Gemini categorization |
| **2 — Backend API** | ✅ Done | Rust + Axum REST API (tweets list/filter/detail + stats) |
| **3 — Dashboard** | ✅ Done | Rust + Dioxus 0.7 web frontend with category pills and detail view |
| **4 — Automation** | 🔜 Next | Scheduled scrape + categorize (cron / Supabase Edge Functions) |

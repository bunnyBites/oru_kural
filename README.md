# ஒரு குரல் — Oru Kural

**One Voice** — A civic tech window into what Tamil Nadu citizens are saying to their Chief Minister.

Oru Kural scrapes public tweets mentioning the Tamil Nadu CM's official X handle (@CMofTamilNadu), uses AI to categorize them by topic (infrastructure, health, education, complaints, and more), and surfaces the results in a live dashboard — turning the noise of social media into structured civic signal.

---

## Architecture

```
  X / Twitter
      │
      │  (Apify actor: apidojo/tweet-scraper)
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
                                  Axum REST API  (Phase 2)
                                            │
                                            ▼
                                  Dioxus Dashboard  (Phase 3)
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
#   SUPABASE_URL        — project URL from Supabase dashboard
#   SUPABASE_ANON_KEY   — anon/public key from Supabase dashboard
#   GEMINI_API_KEY      — Google AI Studio key
#   APIFY_API_KEY       — Apify console → Settings → Integrations
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
# Step 1 — scrape (triggers Apify, polls until done, upserts to Supabase)
python scrape_tweets.py

# Step 1 (dry-run, no Apify credits) — load from a local JSON file
python scrape_tweets.py --dry-run sample_data.json

# Step 2 — categorize all uncategorized tweets with Gemini
python categorize_tweets.py
```

---

## Phase roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **1 — Data pipeline** | ✅ Done | Apify scraper → Supabase, Gemini categorization |
| **2 — Backend API** | 🔜 Next | Rust + Axum REST API over the tweets table |
| **3 — Dashboard** | 🔜 | Rust + Dioxus web frontend with category filters and charts |
| **4 — Automation** | 🔜 | Scheduled scrape + categorize (cron / Supabase Edge Functions) |

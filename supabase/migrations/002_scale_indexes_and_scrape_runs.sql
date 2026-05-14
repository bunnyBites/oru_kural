-- Full-text search on tweet content (Tamil + English)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_tweets_content_trgm
  ON tweets USING GIN (content gin_trgm_ops);

-- Fast filter: category + recency (most common dashboard query)
CREATE INDEX IF NOT EXISTS idx_tweets_category_posted_at
  ON tweets (category, posted_at DESC)
  WHERE category IS NOT NULL;

-- Fast filter: uncategorized tweets (used by categorize_tweets.py)
CREATE INDEX IF NOT EXISTS idx_tweets_uncategorized
  ON tweets (scraped_at DESC)
  WHERE category IS NULL;

-- Scrape run tracking table
CREATE TABLE IF NOT EXISTS scrape_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  tweets_fetched INT DEFAULT 0,
  tweets_upserted INT DEFAULT 0,
  pages_fetched INT DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed
  error_message TEXT,
  script TEXT NOT NULL                      -- 'scrape_tweets' | 'categorize_tweets'
);

-- Unified citizen signals table (replaces tweets — supports X and Reddit)
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'x',     -- 'x' | 'reddit'
  author_handle TEXT,
  author_name TEXT,
  content TEXT NOT NULL,
  translated_content TEXT,
  url TEXT,                              -- direct link to original post
  posted_at TIMESTAMPTZ,
  category TEXT,
  confidence FLOAT,
  issue_id BIGINT REFERENCES issues(id),
  score INT,                             -- likes (X) or upvote score (Reddit)
  raw_json JSONB,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- Migrate all existing tweets into signals as source='x'
INSERT INTO signals (
  id, source, author_handle, author_name, content, translated_content,
  url, posted_at, category, confidence, issue_id, score, raw_json, scraped_at
)
SELECT
  id,
  'x',
  author_handle,
  author_name,
  content,
  translated_content,
  'https://twitter.com/i/web/status/' || id,
  posted_at,
  category,
  confidence,
  issue_id,
  (raw_json -> 'public_metrics' ->> 'like_count')::INT,
  raw_json,
  scraped_at
FROM tweets
ON CONFLICT (id) DO NOTHING;

-- Signal ↔ Issue mapping (replaces tweet_issue_map)
CREATE TABLE IF NOT EXISTS signal_issue_map (
  signal_id TEXT REFERENCES signals(id),
  issue_id BIGINT REFERENCES issues(id),
  similarity_score FLOAT,
  PRIMARY KEY (signal_id, issue_id)
);

-- Migrate existing tweet_issue_map into signal_issue_map
INSERT INTO signal_issue_map (signal_id, issue_id, similarity_score)
SELECT tweet_id, issue_id, similarity_score FROM tweet_issue_map
ON CONFLICT DO NOTHING;

-- Indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_signals_posted_at
  ON signals (posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_signals_category_posted
  ON signals (category, posted_at DESC)
  WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_signals_uncategorized
  ON signals (scraped_at DESC)
  WHERE category IS NULL;

CREATE INDEX IF NOT EXISTS idx_signals_unclustered
  ON signals (posted_at DESC)
  WHERE issue_id IS NULL AND category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_signals_source
  ON signals (source, posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_signals_content_trgm
  ON signals USING GIN (content gin_trgm_ops);

-- Update category_stats — seed any missing categories for new schema
INSERT INTO category_stats (category, issue_count, open_count, resolved_count, tweet_count)
VALUES
  ('Demand', 0, 0, 0, 0), ('Complaint', 0, 0, 0, 0), ('Public Event', 0, 0, 0, 0),
  ('Welcome', 0, 0, 0, 0), ('Infrastructure', 0, 0, 0, 0), ('Health', 0, 0, 0, 0),
  ('Education', 0, 0, 0, 0), ('Criticism', 0, 0, 0, 0), ('Other', 0, 0, 0, 0)
ON CONFLICT (category) DO NOTHING;

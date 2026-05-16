-- Add issue_id column to tweets
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS issue_id BIGINT;

-- Issues: clustered citizen demands/complaints
CREATE TABLE IF NOT EXISTS issues (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT,
  category TEXT NOT NULL,
  location TEXT,
  department TEXT,
  status TEXT NOT NULL DEFAULT 'open',          -- open | acknowledged | in_progress | resolved
  voice_count INT NOT NULL DEFAULT 1,
  first_raised_at TIMESTAMPTZ NOT NULL,
  last_updated_at TIMESTAMPTZ DEFAULT NOW(),
  linked_event_id BIGINT,
  resolution_note TEXT
);

-- CM Events: official TN Government press releases and news
CREATE TABLE IF NOT EXISTS cm_events (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  event_date TIMESTAMPTZ,
  location TEXT,
  department TEXT,
  category TEXT,
  source_url TEXT NOT NULL UNIQUE,
  source_name TEXT,
  linked_issue_id BIGINT,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tweet ↔ Issue mapping (many tweets can belong to one issue)
CREATE TABLE IF NOT EXISTS tweet_issue_map (
  tweet_id TEXT REFERENCES tweets(id),
  issue_id BIGINT REFERENCES issues(id),
  similarity_score FLOAT,
  PRIMARY KEY (tweet_id, issue_id)
);

-- Extend category_stats to track issue counts
ALTER TABLE category_stats ADD COLUMN IF NOT EXISTS issue_count INT DEFAULT 0;
ALTER TABLE category_stats ADD COLUMN IF NOT EXISTS open_count INT DEFAULT 0;
ALTER TABLE category_stats ADD COLUMN IF NOT EXISTS resolved_count INT DEFAULT 0;

-- Index: fast lookup of unclustered actionable tweets
CREATE INDEX IF NOT EXISTS idx_tweets_unclustered
  ON tweets (posted_at DESC)
  WHERE issue_id IS NULL AND category IS NOT NULL;

-- Index: open issues by recency
CREATE INDEX IF NOT EXISTS idx_issues_status_updated
  ON issues (status, last_updated_at DESC);

-- Index: unlinked cm_events
CREATE INDEX IF NOT EXISTS idx_cm_events_unlinked
  ON cm_events (event_date DESC)
  WHERE linked_issue_id IS NULL;

-- Function: atomically increment voice_count on an issue
CREATE OR REPLACE FUNCTION increment_issue_voices(p_issue_id BIGINT, p_count INT)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE issues
  SET voice_count = voice_count + p_count,
      last_updated_at = NOW()
  WHERE id = p_issue_id;
END;
$$;

-- Function: refresh issue counts in category_stats
CREATE OR REPLACE FUNCTION refresh_issue_stats()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO category_stats (category, issue_count, open_count, resolved_count, last_updated)
  SELECT
    category,
    COUNT(*),
    COUNT(*) FILTER (WHERE status = 'open'),
    COUNT(*) FILTER (WHERE status = 'resolved'),
    NOW()
  FROM issues
  GROUP BY category
  ON CONFLICT (category)
  DO UPDATE SET
    issue_count    = EXCLUDED.issue_count,
    open_count     = EXCLUDED.open_count,
    resolved_count = EXCLUDED.resolved_count,
    last_updated   = EXCLUDED.last_updated;
END;
$$;

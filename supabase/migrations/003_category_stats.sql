CREATE TABLE IF NOT EXISTS category_stats (
  category TEXT PRIMARY KEY,
  tweet_count INT NOT NULL DEFAULT 0,
  last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed with zeros for all known categories
INSERT INTO category_stats (category, tweet_count)
VALUES
  ('Demand', 0), ('Complaint', 0), ('Public Event', 0),
  ('Welcome', 0), ('Infrastructure', 0), ('Health', 0),
  ('Education', 0), ('Criticism', 0), ('Other', 0)
ON CONFLICT (category) DO NOTHING;

-- Function to refresh stats from live tweets table
CREATE OR REPLACE FUNCTION refresh_category_stats()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO category_stats (category, tweet_count, last_updated)
  SELECT category, COUNT(*), NOW()
  FROM tweets
  WHERE category IS NOT NULL
  GROUP BY category
  ON CONFLICT (category)
  DO UPDATE SET
    tweet_count = EXCLUDED.tweet_count,
    last_updated = EXCLUDED.last_updated;
END;
$$;

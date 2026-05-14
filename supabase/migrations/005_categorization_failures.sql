CREATE TABLE IF NOT EXISTS categorization_failures (
  id BIGSERIAL PRIMARY KEY,
  tweet_ids TEXT[] NOT NULL,
  error_message TEXT NOT NULL,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  batch_size INT NOT NULL,
  resolved BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE categorization_failures IS
  'Tracks Gemini categorization batches that failed.
   tweet_ids are left with category=NULL in tweets table.
   Set resolved=TRUE manually after re-running categorization.';

CREATE TABLE IF NOT EXISTS tweets_archive (
  LIKE tweets INCLUDING ALL
);

-- Function: move tweets older than 90 days to archive
CREATE OR REPLACE FUNCTION archive_old_tweets()
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
  moved_count INT;
BEGIN
  WITH moved AS (
    DELETE FROM tweets
    WHERE posted_at < NOW() - INTERVAL '90 days'
    RETURNING *
  )
  INSERT INTO tweets_archive SELECT * FROM moved;

  GET DIAGNOSTICS moved_count = ROW_COUNT;
  RETURN moved_count;
END;
$$;

COMMENT ON FUNCTION archive_old_tweets() IS
  'Call manually or via pg_cron. Moves tweets older than 90 days to tweets_archive.
   Run after each scrape cycle to keep the live table lean.';

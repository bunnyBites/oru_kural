-- Allow anonymous reads on scrape_runs so the /meta endpoint
-- (which uses SUPABASE_ANON_KEY) can fetch the last pipeline run timestamp.

ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_scrape_runs" ON scrape_runs;
CREATE POLICY "anon_read_scrape_runs" ON scrape_runs FOR SELECT TO anon USING (true);

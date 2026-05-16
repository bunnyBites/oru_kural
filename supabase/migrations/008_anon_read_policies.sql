-- Allow anonymous reads on all public-facing tables.
-- The backend uses SUPABASE_ANON_KEY (read-only), so these tables
-- need SELECT policies for the anon role.

-- signals
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_signals" ON signals;
CREATE POLICY "anon_read_signals" ON signals FOR SELECT TO anon USING (true);

-- issues
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_issues" ON issues;
CREATE POLICY "anon_read_issues" ON issues FOR SELECT TO anon USING (true);

-- cm_events
ALTER TABLE cm_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_cm_events" ON cm_events;
CREATE POLICY "anon_read_cm_events" ON cm_events FOR SELECT TO anon USING (true);

-- category_stats
ALTER TABLE category_stats ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_category_stats" ON category_stats;
CREATE POLICY "anon_read_category_stats" ON category_stats FOR SELECT TO anon USING (true);

-- signal_issue_map
ALTER TABLE signal_issue_map ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_read_signal_issue_map" ON signal_issue_map;
CREATE POLICY "anon_read_signal_issue_map" ON signal_issue_map FOR SELECT TO anon USING (true);

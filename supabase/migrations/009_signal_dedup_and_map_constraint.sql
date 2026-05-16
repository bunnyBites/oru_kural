-- T-19: Ensure signal_issue_map upserts are idempotent across pipeline re-runs.
-- Creates a unique index if the composite PK/unique constraint doesn't already cover it.
CREATE UNIQUE INDEX IF NOT EXISTS signal_issue_map_signal_id_issue_id_idx
    ON signal_issue_map (signal_id, issue_id);

-- T-22: Track duplicate signals to avoid re-categorizing near-identical content.
ALTER TABLE signals
    ADD COLUMN IF NOT EXISTS duplicate_of TEXT REFERENCES signals(id);

CREATE INDEX IF NOT EXISTS signals_duplicate_of_idx ON signals (duplicate_of)
    WHERE duplicate_of IS NOT NULL;

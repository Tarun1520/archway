-- =============================================================================
-- Migration 0003: saved suggestions for a brief version
-- =============================================================================
-- One row per (run, brief version). Saving them means the model is asked once
-- per version, not every time the page is opened or reloaded.
--
-- LEARNING NOTE: a suggestion is the model's idea, not part of the brief, so
-- it lives in its own table and never changes a brief.
-- -----------------------------------------------------------------------------

CREATE TABLE brief_suggestions (
    run_id         TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    brief_version  INTEGER NOT NULL,
    content        TEXT NOT NULL,        -- the cleaned suggestions as JSON text
    created_at     TEXT NOT NULL,
    PRIMARY KEY (run_id, brief_version)
);

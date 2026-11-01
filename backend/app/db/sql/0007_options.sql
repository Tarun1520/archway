-- =============================================================================
-- Migration 0007: Phase 5 architecture options
-- =============================================================================
-- Every VERSION of every option is kept (a revision saves the next version, it
-- never edits one), with its review. The run's options state (was it asked for,
-- what is selected, what the notes say) is one small row.
-- -----------------------------------------------------------------------------

CREATE TABLE option_versions (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,              -- "OPT-1"
    version  INTEGER NOT NULL,
    content  TEXT NOT NULL,              -- ArchitectureOption as JSON (includes its review and whether it is approved)
    PRIMARY KEY (run_id, id, version)
);

CREATE TABLE option_state (
    run_id               TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    requested            INTEGER NOT NULL DEFAULT 0,
    selected_option_id   TEXT,
    notes                TEXT NOT NULL DEFAULT '[]',   -- JSON list of visible explanations
    no_recommendation    INTEGER NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL
);

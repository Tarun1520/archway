-- =============================================================================
-- Migration 0008: Phase 6 build plans
-- =============================================================================
-- One row per approved option VERSION a plan was asked for. A plan belongs to
-- that version: when a newer version is approved, a new row is made and the old
-- one stays as the record of what was planned before. The newest row is the
-- run's current plan.
-- -----------------------------------------------------------------------------

CREATE TABLE plans (
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    option_id   TEXT NOT NULL,                 -- "OPT-1"
    version     INTEGER NOT NULL,              -- the approved version the plan is for
    roadmap     TEXT,                          -- Roadmap as JSON (NULL until planned)
    files       TEXT NOT NULL DEFAULT '[]',    -- JSON list of PromptFile (with each prompt's rubric)
    links       TEXT NOT NULL DEFAULT '[]',    -- JSON list of PlanLink
    export      TEXT,                          -- the whole plan as JSON (NULL until exported)
    passed      INTEGER,                       -- 1 / 0 / NULL (not checked yet)
    outcome     TEXT,                          -- "full" | "partial" | NULL
    notes       TEXT NOT NULL DEFAULT '[]',    -- JSON list of visible explanations
    completed   TEXT NOT NULL DEFAULT '[]',    -- JSON list of prompt paths the person marked as done
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (run_id, option_id, version)
);

-- =============================================================================
-- Migration 0002: tables for the Phase 2 workflow
-- =============================================================================
-- briefs        every version of a run's brief (nothing is overwritten)
-- usage_events  one row per call to an outside service (the usage counters)
-- run_events    the progress events of a run, in order (the activity feed)
--
-- LEARNING NOTE: these are Archway's OWN tables. LangGraph keeps its
-- checkpoints in a separate file (checkpoints.db) that it manages itself.
-- -----------------------------------------------------------------------------

CREATE TABLE briefs (
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    confirmed   INTEGER NOT NULL DEFAULT 0,
    -- The whole brief as JSON text. Pydantic checks it when it is read back.
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    -- A run can have each version number only once.
    PRIMARY KEY (run_id, version)
);

CREATE TABLE usage_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    service          TEXT NOT NULL CHECK (service IN ('llm', 'jev', 'github')),
    mode             TEXT NOT NULL CHECK (mode IN ('live', 'fixture')),
    count            INTEGER NOT NULL CHECK (count >= 1),
    tokens_if_known  INTEGER,            -- NULL when the service did not report tokens
    timestamp        TEXT NOT NULL
);

CREATE INDEX idx_usage_run ON usage_events(run_id, service);

CREATE TABLE run_events (
    -- AUTOINCREMENT gives every event a number that only ever goes up. The
    -- browser remembers the last number it saw and asks for newer ones.
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    data        TEXT NOT NULL,           -- JSON text
    created_at  TEXT NOT NULL
);

CREATE INDEX idx_run_events_run ON run_events(run_id, id);

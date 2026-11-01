-- =============================================================================
-- Migration 0001: the first three tables (projects, messages, runs)
-- =============================================================================
-- LEARNING NOTE: what is a migration?
--   A migration is one numbered step that changes the database structure.
--   The database remembers the number of the last step it applied, so each
--   step runs exactly once, in order. To change the structure later you ADD a
--   new file (0002_...sql). You never edit a migration that has already run.
--
-- LEARNING NOTE: column rules
--   PRIMARY KEY  the unique id of a row
--   NOT NULL     this column must always have a value
--   (no NOT NULL) the column may be NULL, which means "unknown / not set"
--   REFERENCES   this value must be the id of a row in another table
--   ON DELETE CASCADE  deleting a project also deletes its messages and runs
--   CHECK        only these values are allowed
--
-- Dates are stored as text in ISO 8601 format, in UTC,
-- for example 2026-10-13T17:05:00+00:00.
-- -----------------------------------------------------------------------------

CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    idea        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE messages (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- An index makes "all messages of this project" fast to look up.
CREATE INDEX idx_messages_project ON messages(project_id, created_at);

CREATE TABLE runs (
    id               TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status           TEXT NOT NULL CHECK (status IN (
                         'draft', 'researching', 'awaiting_selection', 'building_plan',
                         'completed', 'failed', 'paused', 'cancelled')),
    paused_from      TEXT,
    brief_confirmed  INTEGER NOT NULL DEFAULT 0,   -- SQLite has no true/false: 0 or 1
    outcome          TEXT CHECK (outcome IN ('full', 'partial', 'abstained')),
    outcome_note     TEXT,
    jev_mode         TEXT NOT NULL CHECK (jev_mode IN ('live', 'fixture')),
    llm_mode         TEXT NOT NULL CHECK (llm_mode IN ('live', 'fixture')),
    github_mode      TEXT NOT NULL CHECK (github_mode IN ('live', 'fixture')),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX idx_runs_project ON runs(project_id, created_at);

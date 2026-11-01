-- =============================================================================
-- Migration 0004: the research stage (Phase 3)
-- =============================================================================
-- research_runs   one row per run: the plan, the candidates, the notes
-- repo_evidence   one row per inspected repository
-- evidence_items  one row per quoted source (README, metadata, doc page)
-- github_cache    saved GitHub answers, so repeating a search does not spend
--                 requests, and the ORIGINAL retrieval date is kept
--
-- LEARNING NOTE: the cache is not tied to a run (no run_id): the same README
-- is the same README for every run. It is also never used in fixture mode, so
-- recorded demo data can never leak into live results.
-- -----------------------------------------------------------------------------

CREATE TABLE research_runs (
    run_id      TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    plan        TEXT,                    -- ResearchPlan as JSON, NULL until planned
    candidates  TEXT,                    -- JSON list of Candidate
    shortlist   TEXT,                    -- JSON list of repo names
    notes       TEXT NOT NULL DEFAULT '[]',
    finished    INTEGER NOT NULL DEFAULT 0,
    mode        TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('live', 'fixture')),
    updated_at  TEXT NOT NULL
);

CREATE TABLE repo_evidence (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    repo     TEXT NOT NULL,
    content  TEXT NOT NULL,              -- RepoEvidence as JSON
    PRIMARY KEY (run_id, repo)
);

CREATE TABLE evidence_items (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,
    content  TEXT NOT NULL,              -- EvidenceItem as JSON
    PRIMARY KEY (run_id, id)
);

CREATE TABLE github_cache (
    cache_key     TEXT PRIMARY KEY,      -- a hash of method, URL and parameters
    status_code   INTEGER NOT NULL,
    content_type  TEXT,
    body          TEXT NOT NULL,
    retrieved_at  TEXT NOT NULL          -- when GitHub first answered, kept on every reuse
);

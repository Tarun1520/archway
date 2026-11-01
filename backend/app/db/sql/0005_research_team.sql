-- =============================================================================
-- Migration 0005: the research TEAM (agents) replaces the fixed pipeline
-- =============================================================================
-- The fixed pipeline's columns (plan, candidates, shortlist) are dropped.
-- New: the capabilities and the review on the run row, and one table each
-- for proposed components, similar projects, and the agents' messages.
-- repo_evidence and evidence_items are kept unchanged.
-- -----------------------------------------------------------------------------

ALTER TABLE research_runs DROP COLUMN plan;
ALTER TABLE research_runs DROP COLUMN candidates;
ALTER TABLE research_runs DROP COLUMN shortlist;
ALTER TABLE research_runs ADD COLUMN capabilities TEXT;   -- JSON list of Capability
ALTER TABLE research_runs ADD COLUMN review TEXT;         -- ReviewVerdict as JSON

CREATE TABLE research_components (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,              -- "CMP-1"
    content  TEXT NOT NULL,              -- ComponentCandidate as JSON
    PRIMARY KEY (run_id, id)
);

CREATE TABLE research_projects (
    run_id     TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    reference  TEXT NOT NULL,            -- "owner/name"
    content    TEXT NOT NULL,            -- SimilarProject as JSON
    PRIMARY KEY (run_id, reference)
);

-- The team channel: every task and report the agents sent each other, in order.
CREATE TABLE team_messages (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,
    content  TEXT NOT NULL,              -- TeamMessage as JSON
    PRIMARY KEY (run_id, id)
);

-- =============================================================================
-- Migration 0006: Phase 4 decisions and eligibility
-- =============================================================================
-- One receipt per question asked of the decision model (Jev), including the
-- ones that could not be asked ("not evaluated"), and one eligibility verdict
-- per component from the deterministic gate.
-- -----------------------------------------------------------------------------

CREATE TABLE decision_receipts (
    run_id   TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    id       TEXT NOT NULL,
    content  TEXT NOT NULL,              -- DecisionReceipt as JSON
    PRIMARY KEY (run_id, id)
);

CREATE TABLE eligibility_results (
    run_id        TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    component_id  TEXT NOT NULL,
    content       TEXT NOT NULL,         -- EligibilityResult (+ component_id) as JSON
    PRIMARY KEY (run_id, component_id)
);

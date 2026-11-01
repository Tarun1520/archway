-- =============================================================================
-- Migration 0010: password reset links
-- =============================================================================
-- password_resets  one row per "forgot password" email. The link holds a random
--                  token; only its SHA-256 fingerprint is stored (like sessions),
--                  so a copy of the database cannot be used to reset anything.
--                  A link works once (used_at) and only until expires_at.
-- -----------------------------------------------------------------------------

CREATE TABLE password_resets (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    used_at      TEXT
);
CREATE INDEX idx_password_resets_user ON password_resets(user_id);

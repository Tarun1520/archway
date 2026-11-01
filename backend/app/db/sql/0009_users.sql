-- =============================================================================
-- Migration 0009: accounts, sign-in sessions, and who owns each project
-- =============================================================================
-- users     one row per account. The password is stored only as a salted
--           scrypt hash (app/auth/passwords.py), never as text.
-- sessions  one row per signed-in browser. The browser holds a random token in
--           a cookie; only its SHA-256 fingerprint is stored here, so a copy of
--           the database cannot be used to sign in.
-- projects.owner_id  the account a project belongs to. Projects made before
--           accounts existed have none; the first admin account claims them.
-- -----------------------------------------------------------------------------

CREATE TABLE users (
    id                    TEXT PRIMARY KEY,
    email                 TEXT NOT NULL UNIQUE,          -- stored in lower case
    name                  TEXT,
    password_hash         TEXT NOT NULL,
    role                  TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked')),
    monthly_token_quota   INTEGER,                       -- NULL = no limit
    created_at            TEXT NOT NULL,
    last_seen_at          TEXT
);

CREATE TABLE sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

ALTER TABLE projects ADD COLUMN owner_id TEXT REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_projects_owner ON projects(owner_id);

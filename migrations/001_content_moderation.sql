-- Content moderation, per-user blocklists/strikes, review/retry queues, and AUP acceptance.
-- Run through db.init_db()'s versioned migration runner; duplicate-column errors are idempotent.
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN accepted_aup_version TEXT;
ALTER TABLE users ADD COLUMN accepted_aup_at TEXT;
ALTER TABLE oauth_state ADD COLUMN accepted_aup_version TEXT;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS moderation_log (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    checkpoint TEXT NOT NULL CHECK (checkpoint IN ('save', 'generate', 'send')),
    content_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_excerpt TEXT,
    verdict TEXT NOT NULL CHECK (verdict IN ('allow', 'review', 'block')),
    categories TEXT NOT NULL DEFAULT '[]',
    layer TEXT NOT NULL CHECK (layer IN ('local', 'llm', 'heuristic')),
    action_taken TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_moderation_log_user_time ON moderation_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_moderation_log_verdict ON moderation_log(verdict);

CREATE TABLE IF NOT EXISTS user_strikes (
    user_id INTEGER PRIMARY KEY,
    strike_count INTEGER NOT NULL DEFAULT 0,
    last_strike_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'warned', 'rate_limited', 'suspended')),
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS blocklist (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    phrase TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'und',
    type TEXT NOT NULL CHECK (type IN ('word', 'regex', 'domain')),
    added_by INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blocklist_user ON blocklist(user_id);

CREATE TABLE IF NOT EXISTS moderation_queue (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    checkpoint TEXT NOT NULL CHECK (checkpoint IN ('save', 'generate', 'send')),
    content_type TEXT NOT NULL,
    payload_enc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('retry', 'needs_review', 'blocked', 'delivered', 'cancelled')),
    categories TEXT NOT NULL DEFAULT '[]',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_user_status ON moderation_queue(user_id, status);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_retry ON moderation_queue(status, next_attempt_at);

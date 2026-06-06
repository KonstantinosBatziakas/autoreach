"""
db.py — Central database layer for AutoReach
=============================================
Uses Turso (libsql) when TURSO_DB_URL + TURSO_AUTH_TOKEN are set,
otherwise falls back to local SQLite (for local dev / first boot).

All other modules do:
    from db import get_db, init_db
"""

import os
import sqlite3

TURSO_DB_URL   = os.getenv('TURSO_DB_URL', '')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN', '')

# ── Connection factory ────────────────────────────────────────────────────────

def get_db():
    """Return a DB connection.  Turso if env vars are set, else local SQLite."""
    if TURSO_DB_URL and TURSO_AUTH_TOKEN:
        try:
            import libsql                                   # type: ignore
            conn = libsql.connect(TURSO_DB_URL, auth_token=TURSO_AUTH_TOKEN)
            conn.row_factory = _dict_row_factory
            return conn
        except ImportError:
            pass  # fall through to sqlite3

    # Local SQLite fallback
    data_dir = os.getenv('DATA_DIR', '.')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'autoreach.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _dict_row_factory(cursor, row):
    """Make libsql rows behave like sqlite3.Row (subscriptable by name)."""
    if hasattr(cursor, 'description') and cursor.description:
        cols = [d[0] for d in cursor.description]
        return _DictRow(dict(zip(cols, row)))
    return row


class _DictRow(dict):
    """Dict that also supports row['col'] and row[index] access."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


# ── Schema init ───────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist.  Safe to call on every startup."""
    conn = get_db()
    # libsql uses execute() but not context-manager; use explicit commit
    stmts = [
        # ── Leads / businesses ──────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS businesses (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            address  TEXT DEFAULT '',
            phone    TEXT DEFAULT '',
            website  TEXT DEFAULT '',
            email    TEXT DEFAULT '',
            stage    TEXT DEFAULT 'New',
            notes    TEXT DEFAULT ''
        )""",

        # ── Sent email log ──────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS sent_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            email         TEXT NOT NULL,
            date_sent     TEXT NOT NULL,
            subject       TEXT DEFAULT '',
            body          TEXT DEFAULT ''
        )""",

        # ── Follow-up log ───────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS followup_log (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name      TEXT NOT NULL,
            email              TEXT NOT NULL,
            original_date_sent TEXT NOT NULL,
            followup_step      INTEGER NOT NULL,
            date_sent          TEXT NOT NULL,
            subject            TEXT DEFAULT '',
            body               TEXT DEFAULT ''
        )""",

        # ── Key-value settings (email template, etc.) ───────────────────────
        """CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )""",

        # ── Auth: users ─────────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            provider      TEXT NOT NULL,
            provider_id   TEXT NOT NULL,
            email         TEXT,
            name          TEXT,
            avatar_url    TEXT,
            password_hash TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(provider, provider_id)
        )""",

        # ── Auth: OAuth CSRF state ──────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS oauth_state (
            state      TEXT PRIMARY KEY,
            provider   TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    ]

    for stmt in stmts:
        conn.execute(stmt)
    conn.commit()
    conn.close()

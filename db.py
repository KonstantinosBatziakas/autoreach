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

TURSO_DB_URL    = os.getenv('TURSO_DB_URL', '')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN', '')

# ── Turso wrapper ─────────────────────────────────────────────────────────────
# libsql returns plain tuples with no row_factory support.
# We wrap it so every fetchone/fetchall returns _DictRow objects,
# matching the sqlite3.Row interface used throughout the codebase.

class _DictRow(dict):
    """Dict that also supports integer index access like sqlite3.Row."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _TursoCursor:
    def __init__(self, cursor):
        self._cur = cursor

    @property
    def description(self):
        return self._cur.description

    def _to_dict_row(self, row):
        if row is None:
            return None
        if self._cur.description:
            cols = [d[0] for d in self._cur.description]
            return _DictRow(zip(cols, row))
        return row

    def execute(self, sql, params=()):
        self._cur.execute(sql, params)
        return self

    def fetchone(self):
        return self._to_dict_row(self._cur.fetchone())

    def fetchall(self):
        return [self._to_dict_row(r) for r in self._cur.fetchall()]

    def __iter__(self):
        for row in self._cur.fetchall():
            yield self._to_dict_row(row)


class _TursoConn:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return _TursoCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


# ── Connection factory ────────────────────────────────────────────────────────

def get_db():
    """Return a DB connection. Turso if env vars are set, else local SQLite."""
    if TURSO_DB_URL and TURSO_AUTH_TOKEN:
        try:
            import libsql  # type: ignore
            conn = libsql.connect(TURSO_DB_URL, auth_token=TURSO_AUTH_TOKEN)
            return _TursoConn(conn)
        except ImportError:
            pass  # fall through to sqlite3

    # Local SQLite fallback
    data_dir = os.getenv('DATA_DIR', '.')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'autoreach.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema init ───────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    conn = get_db()
    stmts = [
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
        """CREATE TABLE IF NOT EXISTS sent_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            email         TEXT NOT NULL,
            date_sent     TEXT NOT NULL,
            subject       TEXT DEFAULT '',
            body          TEXT DEFAULT ''
        )""",
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
        """CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )""",
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

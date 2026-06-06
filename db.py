"""
db.py — Central database layer for AutoReach
=============================================
Uses Turso's HTTP API when TURSO_DB_URL + TURSO_AUTH_TOKEN are set.
Falls back to local SQLite for local dev.

All other modules do:
    from db import get_db, init_db
"""

import os
import sqlite3
import json
import requests as _requests

TURSO_DB_URL     = os.getenv('TURSO_DB_URL', '')      # e.g. libsql://autoreach-xxx.turso.io
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN', '')

# Convert libsql:// → https:// for the HTTP API
def _http_url():
    url = TURSO_DB_URL.replace('libsql://', 'https://')
    return url.rstrip('/')


# ── Row wrapper ───────────────────────────────────────────────────────────────

class _DictRow(dict):
    """Dict that also supports integer index access like sqlite3.Row."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


# ── Turso HTTP connection ─────────────────────────────────────────────────────

class _TursoConn:
    """
    Mimics the sqlite3 connection interface but sends SQL to Turso's
    HTTP pipeline API. Statements are queued and flushed on commit().
    """
    def __init__(self):
        self._pending = []   # list of SQL strings + params queued for commit
        self._last_rows = []
        self._last_cols = []

    def execute(self, sql, params=()):
        """
        Execute immediately (for SELECTs) or queue for commit (for writes).
        Returns self so callers can chain .fetchone() / .fetchall().
        """
        stmt = self._build_stmt(sql, params)
        is_read = sql.strip().upper().startswith('SELECT')

        if is_read:
            result = self._pipeline([stmt])
            # result is a list of response dicts from Turso
            # grab the first non-empty one
            res = result[0] if result else {}
            rows_data = res.get('rows', [])
            cols_data = res.get('cols', [])
            self._last_cols = [c['name'] for c in cols_data]
            def _unwrap(cell):
                if not isinstance(cell, dict):
                    return cell
                t = cell.get('type', 'text')
                v = cell.get('value')
                if v is None:
                    return None
                if t == 'integer':
                    try: return int(v)
                    except (ValueError, TypeError): return v
                if t == 'float':
                    try: return float(v)
                    except (ValueError, TypeError): return v
                return v  # text / blob — keep as string

            self._last_rows = [
                _DictRow(zip(self._last_cols, [_unwrap(cell) for cell in r]))
                for r in rows_data
            ]
        else:
            # Queue write — will be sent on commit()
            self._pending.append(stmt)
            self._last_rows = []
            self._last_cols = []

        return self

    def fetchone(self):
        return self._last_rows[0] if self._last_rows else None

    def fetchall(self):
        return list(self._last_rows)

    def commit(self):
        if not self._pending:
            return
        stmts = list(self._pending)
        stmts.append({"type": "close"})
        self._pipeline(stmts)
        self._pending.clear()

    def close(self):
        # Flush any un-committed writes (shouldn't normally happen)
        if self._pending:
            self.commit()

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_stmt(sql, params):
        """Convert sql + params into a Turso pipeline statement object."""
        args = []
        for p in params:
            if p is None:
                args.append({"type": "null", "value": None})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                args.append({"type": "float", "value": p})
            else:
                args.append({"type": "text", "value": str(p)})
        return {"type": "execute", "stmt": {"sql": sql, "args": args}}

    def _pipeline(self, stmts):
        url = _http_url() + '/v2/pipeline'
        headers = {
            'Authorization': f'Bearer {TURSO_AUTH_TOKEN}',
            'Content-Type': 'application/json',
        }
        resp = _requests.post(url, headers=headers,
                              data=json.dumps({"requests": stmts}),
                              timeout=15)
        resp.raise_for_status()
        results = resp.json().get('results', [])
        # Each result has type "ok" or "error"
        out = []
        for r in results:
            if r.get('type') == 'error':
                raise Exception(f"Turso error: {r.get('error', {}).get('message', r)}")
            if r.get('type') == 'ok':
                out.append(r.get('response', {}).get('result', {}))
        return out


# ── Connection factory ────────────────────────────────────────────────────────

def get_db():
    """Return a DB connection. Turso HTTP if env vars are set, else local SQLite."""
    if TURSO_DB_URL and TURSO_AUTH_TOKEN:
        return _TursoConn()

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
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            address      TEXT DEFAULT '',
            phone        TEXT DEFAULT '',
            website      TEXT DEFAULT '',
            email        TEXT DEFAULT '',
            stage        TEXT DEFAULT 'New',
            notes        TEXT DEFAULT '',
            unsubscribed INTEGER DEFAULT 0
        )""",
        # Migration: add column if it doesn't exist yet
        "ALTER TABLE businesses ADD COLUMN unsubscribed INTEGER DEFAULT 0",
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
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception as e:
            # Ignore "duplicate column" / "already exists" from migrations
            msg = str(e).lower()
            if 'duplicate column' in msg or 'already exists' in msg:
                if hasattr(conn, '_pending'):
                    conn._pending.clear()   # discard queued Turso stmt
            else:
                raise
    conn.close()

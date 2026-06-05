"""
SQLite database layer for AutoReach.
Replaces businesses.csv and sent_log.csv with a proper local DB.
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".autoreach" / "autoreach.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
    -- Multi-sender account pool
    CREATE TABLE IF NOT EXISTS sender_accounts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT NOT NULL UNIQUE,
        app_password  TEXT NOT NULL,
        daily_limit   INTEGER NOT NULL DEFAULT 150,
        enabled       INTEGER NOT NULL DEFAULT 1,   -- 1=on, 0=off
        notes         TEXT DEFAULT '',
        added_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS leads (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        address     TEXT DEFAULT '',
        phone       TEXT DEFAULT '',
        website     TEXT DEFAULT '',
        email       TEXT DEFAULT '',
        status      TEXT DEFAULT 'new',
        added_at    TEXT DEFAULT (datetime('now')),
        notes       TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS sent_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id         INTEGER REFERENCES leads(id),
        business_name   TEXT NOT NULL,
        email           TEXT NOT NULL,
        subject         TEXT,
        body            TEXT,
        language        TEXT DEFAULT 'english',
        status          TEXT DEFAULT 'sent',
        sender_email    TEXT DEFAULT '',
        sent_at         TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    -- Follow-up sequences: tracks each scheduled/sent follow-up per lead
    CREATE TABLE IF NOT EXISTS followups (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id         INTEGER REFERENCES leads(id),
        business_name   TEXT NOT NULL,
        email           TEXT NOT NULL,
        sequence_num    INTEGER NOT NULL DEFAULT 1,  -- 1, 2, or 3
        status          TEXT NOT NULL DEFAULT 'pending',  -- pending/sent/skipped/replied
        language        TEXT DEFAULT 'english',
        subject         TEXT DEFAULT '',
        body            TEXT DEFAULT '',
        scheduled_for   TEXT NOT NULL,   -- ISO date when it should be sent
        sent_at         TEXT DEFAULT ''
    );

    -- Reply log: emails from leads detected via IMAP
    CREATE TABLE IF NOT EXISTS replies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id     INTEGER REFERENCES leads(id),
        email       TEXT NOT NULL,
        detected_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    _migrate(conn)


def _migrate(conn: sqlite3.Connection):
    """Idempotent ALTER TABLE migrations for schema additions."""
    # Add sender_email column to sent_log if missing (pre-rotation installs)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sent_log)")}
    if "sender_email" not in cols:
        conn.execute("ALTER TABLE sent_log ADD COLUMN sender_email TEXT DEFAULT ''")
        conn.commit()


# ── Leads ──────────────────────────────────────────────────────────────────

def get_leads(conn, with_email_only=False):
    if with_email_only:
        return conn.execute(
            """SELECT * FROM leads
               WHERE email != '' AND email IS NOT NULL
               AND status != 'unsubscribed'
               ORDER BY id"""
        ).fetchall()
    return conn.execute("SELECT * FROM leads ORDER BY id").fetchall()


def add_lead(conn, name, address="", phone="", website="", email="", notes=""):
    conn.execute(
        "INSERT INTO leads (name, address, phone, website, email, notes) VALUES (?,?,?,?,?,?)",
        (name, address, phone, website, email, notes)
    )
    conn.commit()


def update_lead_email(conn, lead_id, email):
    conn.execute("UPDATE leads SET email=? WHERE id=?", (email, lead_id))
    conn.commit()


def bulk_insert_leads(conn, rows: list[dict]):
    """rows: list of dicts with keys name/address/phone/website/email"""
    conn.executemany(
        "INSERT INTO leads (name, address, phone, website, email) VALUES (:name,:address,:phone,:website,:email)",
        rows
    )
    conn.commit()


def export_leads_csv(conn, path: str):
    import csv
    leads = get_leads(conn)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "address", "phone", "website", "email", "status", "added_at"])
        for r in leads:
            w.writerow([r["id"], r["name"], r["address"], r["phone"],
                        r["website"], r["email"], r["status"], r["added_at"]])
    return path


# ── Sent log ───────────────────────────────────────────────────────────────

def get_sent_emails_set(conn) -> set:
    rows = conn.execute("SELECT email FROM sent_log").fetchall()
    return {r["email"].lower() for r in rows}


def log_sent(conn, lead_id, business_name, email, subject, body, language,
             status="sent", sender_email=""):
    conn.execute(
        """INSERT INTO sent_log
           (lead_id, business_name, email, subject, body, language, status, sender_email)
           VALUES (?,?,?,?,?,?,?,?)""",
        (lead_id, business_name, email, subject, body, language, status, sender_email)
    )
    conn.commit()


def get_analytics(conn) -> dict:
    total_leads   = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    with_email    = conn.execute("SELECT COUNT(*) FROM leads WHERE email != ''").fetchone()[0]
    total_sent    = conn.execute("SELECT COUNT(*) FROM sent_log WHERE status='sent'").fetchone()[0]
    total_failed  = conn.execute("SELECT COUNT(*) FROM sent_log WHERE status='failed'").fetchone()[0]
    today         = datetime.now().strftime("%Y-%m-%d")
    sent_today    = conn.execute(
        "SELECT COUNT(*) FROM sent_log WHERE status='sent' AND sent_at LIKE ?",
        (f"{today}%",)
    ).fetchone()[0]
    return {
        "total_leads":  total_leads,
        "with_email":   with_email,
        "total_sent":   total_sent,
        "total_failed": total_failed,
        "sent_today":   sent_today,
    }


# ── Sender accounts ───────────────────────────────────────────────────────

def add_sender_account(conn, email: str, app_password: str,
                       daily_limit: int = 150, notes: str = "") -> int:
    cur = conn.execute(
        """INSERT INTO sender_accounts (email, app_password, daily_limit, notes)
           VALUES (?,?,?,?)
           ON CONFLICT(email) DO UPDATE SET
               app_password=excluded.app_password,
               daily_limit=excluded.daily_limit,
               notes=excluded.notes""",
        (email, app_password, daily_limit, notes)
    )
    conn.commit()
    return cur.lastrowid


def get_sender_accounts(conn) -> list:
    return conn.execute(
        "SELECT * FROM sender_accounts ORDER BY id"
    ).fetchall()


def get_enabled_sender_accounts(conn) -> list:
    return conn.execute(
        "SELECT * FROM sender_accounts WHERE enabled=1 ORDER BY id"
    ).fetchall()


def set_sender_account_enabled(conn, account_id: int, enabled: bool):
    conn.execute(
        "UPDATE sender_accounts SET enabled=? WHERE id=?",
        (1 if enabled else 0, account_id)
    )
    conn.commit()


def remove_sender_account(conn, account_id: int):
    conn.execute("DELETE FROM sender_accounts WHERE id=?", (account_id,))
    conn.commit()


def get_sender_sent_today(conn, sender_email: str) -> int:
    """Count emails sent by a specific sender address today."""
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        """SELECT COUNT(*) FROM sent_log
           WHERE status='sent'
             AND sender_email=?
             AND sent_at LIKE ?""",
        (sender_email, f"{today}%")
    ).fetchone()
    return row[0] if row else 0


def get_all_senders_today_counts(conn) -> dict:
    """Returns {email: sends_today} for all sender accounts."""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT sender_email, COUNT(*) as cnt
           FROM sent_log
           WHERE status='sent' AND sent_at LIKE ?
           GROUP BY sender_email""",
        (f"{today}%",)
    ).fetchall()
    return {r["sender_email"]: r["cnt"] for r in rows}


# ── Config ─────────────────────────────────────────────────────────────────

def get_config(conn, key, default=None):
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_config(conn, key, value):
    conn.execute(
        "INSERT INTO config (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    conn.commit()


def get_all_config(conn) -> dict:
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ── Follow-up sequences ────────────────────────────────────────────────────

def schedule_followups(conn, lead_id: int, business_name: str, email: str,
                        language: str, delays: list[int]):
    """
    Called right after the initial email is sent.
    delays = [days_until_followup_1, days_until_followup_2, days_until_followup_3]
    e.g. [3, 7, 14]
    """
    from datetime import timedelta
    now = datetime.now()
    # Remove any existing pending follow-ups for this lead (idempotent)
    conn.execute(
        "DELETE FROM followups WHERE lead_id=? AND status='pending'", (lead_id,)
    )
    for i, days in enumerate(delays, start=1):
        scheduled = (now + timedelta(days=days)).strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO followups
               (lead_id, business_name, email, sequence_num, status, language, scheduled_for)
               VALUES (?,?,?,?,?,?,?)""",
            (lead_id, business_name, email, i, "pending", language, scheduled)
        )
    conn.commit()


def get_due_followups(conn) -> list:
    """Returns all pending follow-ups whose scheduled_for date has arrived."""
    today = datetime.now().strftime("%Y-%m-%d")
    return conn.execute(
        """SELECT f.*, l.name as lead_name, l.address
           FROM followups f
           JOIN leads l ON l.id = f.lead_id
           WHERE f.status = 'pending'
             AND f.scheduled_for <= ?
           ORDER BY f.scheduled_for, f.sequence_num""",
        (today,)
    ).fetchall()


def get_all_followups(conn) -> list:
    return conn.execute(
        """SELECT f.*, l.name as lead_name
           FROM followups f
           JOIN leads l ON l.id = f.lead_id
           ORDER BY f.scheduled_for DESC"""
    ).fetchall()


def mark_followup_sent(conn, followup_id: int, subject: str, body: str):
    conn.execute(
        """UPDATE followups SET status='sent', subject=?, body=?, sent_at=datetime('now')
           WHERE id=?""",
        (subject, body, followup_id)
    )
    conn.commit()


def mark_followup_skipped(conn, followup_id: int):
    conn.execute("UPDATE followups SET status='skipped' WHERE id=?", (followup_id,))
    conn.commit()


def mark_lead_replied(conn, lead_id: int, email: str):
    """Mark all pending follow-ups cancelled and log the reply."""
    conn.execute(
        "UPDATE followups SET status='replied' WHERE lead_id=? AND status='pending'",
        (lead_id,)
    )
    conn.execute(
        "UPDATE leads SET status='replied' WHERE id=?", (lead_id,)
    )
    # Avoid duplicate reply entries
    existing = conn.execute(
        "SELECT id FROM replies WHERE lead_id=?", (lead_id,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO replies (lead_id, email) VALUES (?,?)", (lead_id, email)
        )
    conn.commit()


def has_replied(conn, lead_id: int) -> bool:
    return conn.execute(
        "SELECT id FROM replies WHERE lead_id=?", (lead_id,)
    ).fetchone() is not None


def get_followup_analytics(conn) -> dict:
    total     = conn.execute("SELECT COUNT(*) FROM followups").fetchone()[0]
    sent      = conn.execute("SELECT COUNT(*) FROM followups WHERE status='sent'").fetchone()[0]
    pending   = conn.execute("SELECT COUNT(*) FROM followups WHERE status='pending'").fetchone()[0]
    replied   = conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
    skipped   = conn.execute("SELECT COUNT(*) FROM followups WHERE status='skipped'").fetchone()[0]
    return {
        "total": total, "sent": sent, "pending": pending,
        "replied": replied, "skipped": skipped,
    }

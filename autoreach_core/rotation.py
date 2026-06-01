"""
Sender account rotation for AutoReach.

Picks the next Gmail account to send from using a fair round-robin
strategy: always select the enabled account with the fewest sends
today that hasn't yet hit its daily_limit.

Falls back to the legacy single-account config (gmail_user /
gmail_app_password) when no sender_accounts rows exist, so existing
single-account setups keep working without any migration step.
"""

from __future__ import annotations
from autoreach_core import db


class NoSendersAvailable(Exception):
    """Raised when no enabled account has remaining daily capacity."""
    pass


def get_next_sender(conn) -> tuple[str, str]:
    """
    Returns (gmail_user, gmail_app_password) for the account that should
    send the next email.

    Selection logic:
      1. Get all enabled sender_accounts.
      2. Query today's send counts per account.
      3. Filter out accounts at or over their daily_limit.
      4. Pick the account with the lowest sends-today (ties broken by
         account id — lowest id first, giving stable round-robin order
         across a day's quota).
      5. If the sender_accounts table is empty, fall back to legacy
         config keys (gmail_user / gmail_app_password).

    Raises NoSendersAvailable if every enabled account is at its daily
    limit, or if no accounts/legacy credentials are configured at all.
    """
    accounts = db.get_enabled_sender_accounts(conn)

    # ── Legacy single-account fallback ────────────────────────────────
    if not accounts:
        cfg = db.get_all_config(conn)
        user = cfg.get("gmail_user", "")
        pwd  = cfg.get("gmail_app_password", "")
        if not user or not pwd:
            raise NoSendersAvailable(
                "No sender accounts configured. Add one with:\n"
                "  autoreach accounts add  (CLI)\n"
                "  or the Accounts tab in the desktop app."
            )
        return user, pwd

    # ── Pool rotation ──────────────────────────────────────────────────
    today_counts = db.get_all_senders_today_counts(conn)

    candidates = []
    for acct in accounts:
        sent_today = today_counts.get(acct["email"], 0)
        if sent_today < acct["daily_limit"]:
            candidates.append((sent_today, acct["id"], acct))

    if not candidates:
        limits = ", ".join(
            f"{a['email']} ({a['daily_limit']}/day)" for a in accounts
        )
        raise NoSendersAvailable(
            f"All sender accounts have reached their daily limit: {limits}"
        )

    # Sort by (sends_today ASC, id ASC) → fairest distribution
    candidates.sort(key=lambda x: (x[0], x[1]))
    chosen = candidates[0][2]
    return chosen["email"], chosen["app_password"]


def get_all_sender_capacity(conn) -> list[dict]:
    """
    Returns a summary of every sender account's daily capacity.
    Useful for dashboards and status displays.

    Each dict has: email, daily_limit, sent_today, remaining, enabled.
    """
    accounts     = db.get_sender_accounts(conn)
    today_counts = db.get_all_senders_today_counts(conn)

    # If no accounts exist, synthesise a row from legacy config
    if not accounts:
        cfg  = db.get_all_config(conn)
        user = cfg.get("gmail_user", "")
        if not user:
            return []
        limit     = int(cfg.get("daily_limit", "150"))
        sent      = today_counts.get(user, 0)
        return [{
            "id":          None,
            "email":       user,
            "daily_limit": limit,
            "sent_today":  sent,
            "remaining":   max(0, limit - sent),
            "enabled":     True,
            "notes":       "(legacy single-account config)",
        }]

    result = []
    for acct in accounts:
        sent = today_counts.get(acct["email"], 0)
        result.append({
            "id":          acct["id"],
            "email":       acct["email"],
            "daily_limit": acct["daily_limit"],
            "sent_today":  sent,
            "remaining":   max(0, acct["daily_limit"] - sent),
            "enabled":     bool(acct["enabled"]),
            "notes":       acct["notes"] or "",
        })
    return result


def total_remaining_today(conn) -> int:
    """Sum of remaining capacity across all enabled accounts."""
    return sum(
        s["remaining"] for s in get_all_sender_capacity(conn)
        if s["enabled"]
    )

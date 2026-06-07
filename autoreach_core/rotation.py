"""
Sender configuration for AutoReach desktop/CLI.

With Resend there is no per-account daily rate limit enforced at the
SMTP level, so the old Gmail round-robin pool is replaced by a single
(resend_api_key, from_email) pair read from config.

The module keeps the same public interface so the rest of the codebase
requires minimal changes:

  get_next_sender(conn)          → (resend_api_key, from_email)
  get_all_sender_capacity(conn)  → list[dict]  (single synthetic row)
  total_remaining_today(conn)    → int  (daily_limit − sent_today)
  NoSendersAvailable             → raised when keys are missing
"""

from __future__ import annotations
from autoreach_core import db


class NoSendersAvailable(Exception):
    """Raised when Resend credentials are not configured."""
    pass


def get_next_sender(conn) -> tuple[str, str]:
    """
    Returns (resend_api_key, from_email) from config.

    Raises NoSendersAvailable if resend_api_key is not set.
    """
    cfg = db.get_all_config(conn)
    key  = cfg.get("resend_api_key", "")
    frm  = cfg.get("from_email", "")

    if not key:
        raise NoSendersAvailable(
            "Resend API key is not configured.\n"
            "Run:  autoreach config  (CLI)\n"
            "or go to Settings in the desktop app."
        )

    if not frm:
        frm = "onboarding@resend.dev"

    return key, frm


def get_all_sender_capacity(conn) -> list[dict]:
    """
    Returns a single-element list summarising the Resend sender.
    Keeps the same dict shape as the old Gmail rotation so dashboards
    and stats views work unchanged.
    """
    cfg = db.get_all_config(conn)
    key  = cfg.get("resend_api_key", "")
    frm  = cfg.get("from_email", "onboarding@resend.dev")

    if not key:
        return []

    limit     = int(cfg.get("daily_limit", "500"))
    today_counts = db.get_all_senders_today_counts(conn)
    sent      = today_counts.get(frm, 0)

    return [{
        "id":          None,
        "email":       frm,
        "daily_limit": limit,
        "sent_today":  sent,
        "remaining":   max(0, limit - sent),
        "enabled":     True,
        "notes":       "Resend API",
    }]


def total_remaining_today(conn) -> int:
    """Remaining daily capacity for the configured Resend sender."""
    capacity = get_all_sender_capacity(conn)
    if not capacity:
        return 0
    return capacity[0]["remaining"]

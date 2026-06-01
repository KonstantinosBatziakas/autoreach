#!/usr/bin/env python3
"""
AutoReach CLI
─────────────
pip install autoreach-cli
autoreach --help
"""

import argparse
import sys
import os
import time
import textwrap
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoreach_core import db
from autoreach_core.emailer     import generate_email, build_html, send_email, DELAY_BETWEEN, MAX_PER_RUN
from autoreach_core.lead_finder import find_businesses
from autoreach_core.scraper     import scrape_leads
from autoreach_core.followup    import run_due_followups, DEFAULT_DELAYS
from autoreach_core.rotation    import get_next_sender, get_all_sender_capacity, total_remaining_today, NoSendersAvailable

# ── Colours ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
WHITE  = "\033[97m"

def c(text, colour):
    return f"{colour}{text}{RESET}"

def header():
    print()
    print(c("  ╔═══════════════════════════════╗", CYAN))
    print(c("  ║  ", CYAN) + c("AUTO", WHITE) + c("REACH", RED) + c("  — AI Cold Outreach  ║", CYAN))
    print(c("  ╚═══════════════════════════════╝", CYAN))
    print()

def divider():
    print(c("  ─────────────────────────────────────────", DIM))

def success(msg): print(c(f"  ✓  {msg}", GREEN))
def warn(msg):    print(c(f"  ⚠  {msg}", YELLOW))
def error(msg):   print(c(f"  ✗  {msg}", RED))
def info(msg):    print(c(f"  →  {msg}", CYAN))
def dim(msg):     print(c(f"     {msg}", DIM))


# ── Config helpers ────────────────────────────────────────────────────────

def require_config(conn, *keys):
    cfg = db.get_all_config(conn)
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        error(f"Missing config: {', '.join(missing)}")
        info("Run:  autoreach config  to set your API keys.")
        sys.exit(1)
    return cfg


# ── Sub-commands ──────────────────────────────────────────────────────────

def cmd_config(args, conn):
    """Interactively set API keys and settings."""
    header()
    print(c("  API Key Setup", BOLD))
    divider()
    print(c("  Press Enter to keep the current value.\n", DIM))

    fields = [
        ("groq_api_key",        "Groq API key"),
        ("gmail_user",          "Gmail address"),
        ("gmail_app_password",  "Gmail App Password"),
        ("google_maps_api_key", "Google Maps API key"),
        ("daily_limit",         "Max emails per day (default 30)"),
        ("delay_seconds",       "Seconds between sends (default 8)"),
        ("followup_delays",     "Follow-up delays in days (default 3,7,14)"),
    ]

    for key, label in fields:
        current = db.get_config(conn, key, "")
        display = ("*" * 8 + current[-4:]) if current and "password" in key.lower() or "key" in key.lower() else current
        prompt  = f"  {label}"
        if display:
            prompt += c(f" [{display}]", DIM)
        prompt += ": "
        val = input(prompt).strip()
        if val:
            db.set_config(conn, key, val)

    success("Config saved to ~/.autoreach/autoreach.db")


def cmd_accounts(args, conn):
    """Manage sender accounts for round-robin rotation."""
    header()
    sub = args.accounts_cmd

    if sub == "list" or sub is None:
        capacity = get_all_sender_capacity(conn)
        if not capacity:
            warn("No sender accounts configured.")
            info("Add one:  autoreach accounts add")
            return
        print(c(f"  {'#':<4} {'Email':<35} {'Limit':>6} {'Today':>6} {'Left':>6} Status", BOLD + WHITE))
        divider()
        for s in capacity:
            status_c = GREEN if s["enabled"] else DIM
            status_t = "on " if s["enabled"] else "off"
            remaining_c = GREEN if s["remaining"] > 0 else RED
            id_str = str(s["id"]) if s["id"] else "—"
            print(
                f"  {id_str:<4} {s['email'][:33]:<35} "
                f"{c(str(s['daily_limit']), DIM):>6}  "
                f"{c(str(s['sent_today']), YELLOW):>6}  "
                f"{c(str(s['remaining']), remaining_c):>6}  "
                f"{c(status_t, status_c)}"
            )
        divider()
        total_rem = total_remaining_today(conn)
        total_lim = sum(s["daily_limit"] for s in capacity if s["enabled"])
        dim(f"Combined remaining today: {total_rem} / {total_lim}")

    elif sub == "add":
        email = getattr(args, "email", None) or input(c("  Gmail address: ", CYAN)).strip()
        pwd   = getattr(args, "password", None) or input(c("  App Password:  ", CYAN)).strip()
        if not email or not pwd:
            error("Email and password are required.")
            sys.exit(1)
        limit_str = getattr(args, "limit", None)
        limit = int(limit_str) if limit_str else 150
        notes = getattr(args, "notes", None) or ""
        db.add_sender_account(conn, email, pwd, limit, notes)
        success(f"Added {email}  (daily limit: {limit})")

    elif sub == "remove":
        acct_id = getattr(args, "id", None)
        if acct_id is None:
            error("Provide account id:  autoreach accounts remove --id N")
            sys.exit(1)
        db.remove_sender_account(conn, int(acct_id))
        success(f"Removed account #{acct_id}")

    elif sub == "enable":
        acct_id = getattr(args, "id", None)
        if acct_id is None:
            error("Provide account id:  autoreach accounts enable --id N")
            sys.exit(1)
        db.set_sender_account_enabled(conn, int(acct_id), True)
        success(f"Account #{acct_id} enabled.")

    elif sub == "disable":
        acct_id = getattr(args, "id", None)
        if acct_id is None:
            error("Provide account id:  autoreach accounts disable --id N")
            sys.exit(1)
        db.set_sender_account_enabled(conn, int(acct_id), False)
        success(f"Account #{acct_id} disabled.")

    else:
        error(f"Unknown accounts sub-command: {sub}")
        info("Usage:  autoreach accounts [list|add|remove|enable|disable]")


def cmd_find(args, conn):
    """Find leads from Google Maps."""
    header()
    cfg = require_config(conn, "google_maps_api_key")

    city          = args.city or input(c("  City: ", CYAN)).strip()
    business_type = args.type or input(c("  Business type: ", CYAN)).strip()

    if not city or not business_type:
        error("City and business type are required.")
        sys.exit(1)

    info(f"Searching Google Maps for '{business_type}' in '{city}'...")
    try:
        results = find_businesses(city, business_type, cfg["google_maps_api_key"])
    except Exception as e:
        error(f"Google Maps error: {e}")
        sys.exit(1)

    db.bulk_insert_leads(conn, results)
    success(f"Found and saved {len(results)} leads.")
    divider()
    for r in results[:5]:
        dim(f"{r['name']} — {r['address']}")
    if len(results) > 5:
        dim(f"... and {len(results)-5} more.")


def cmd_scrape(args, conn):
    """Scrape emails from lead websites."""
    header()
    leads = [dict(r) for r in db.get_leads(conn)]
    no_email = [l for l in leads if not l.get("email")]

    if not no_email:
        warn("All leads already have emails.")
        return

    info(f"Scraping emails for {len(no_email)} leads...")
    divider()

    found = 0
    for i, lead in enumerate(no_email):
        print(f"  [{i+1}/{len(no_email)}] {lead['name'][:40]:<40}", end="\r")
        from autoreach_core.scraper import find_email_for_website
        email = find_email_for_website(lead.get("website", ""))
        if email:
            db.update_lead_email(conn, lead["id"], email)
            found += 1
            success(f"[{i+1}/{len(no_email)}] {lead['name'][:35]} → {email}")
        else:
            dim(f"[{i+1}/{len(no_email)}] {lead['name'][:35]} — none found")
        time.sleep(2)

    divider()
    success(f"Done. Found {found} new emails.")


def cmd_send(args, conn):
    """Generate, preview, and send cold emails."""
    header()
    cfg = require_config(conn, "groq_api_key")

    delay_secs = int(db.get_config(conn, "delay_seconds", str(DELAY_BETWEEN)))
    language   = args.language or "english"
    auto       = args.auto

    # Check sender capacity
    try:
        get_next_sender(conn)  # dry-run
    except NoSendersAvailable as e:
        error(str(e))
        sys.exit(1)

    remaining_today = total_remaining_today(conn)
    if remaining_today <= 0:
        warn("All sender accounts have reached their daily limit.")
        info("Check status with:  autoreach accounts list")
        return

    leads    = [dict(r) for r in db.get_leads(conn, with_email_only=True)]
    sent_set = db.get_sent_emails_set(conn)
    pending  = [l for l in leads if l["email"].lower() not in sent_set]

    if not pending:
        warn("No new leads to email. Find more with:  autoreach find")
        return

    pending = pending[:remaining_today]

    capacity = get_all_sender_capacity(conn)
    acct_summary = ", ".join(f"{s['email']} ({s['remaining']} left)" for s in capacity if s["enabled"])
    info(f"{len(pending)} leads queued  ·  language: {language}  ·  delay: {delay_secs}s")
    info(f"Senders: {acct_summary}")
    divider()

    sent_count   = 0
    failed_count = 0

    for i, lead in enumerate(pending):
        print()
        print(c(f"  [{i+1}/{len(pending)}] {lead['name']}", BOLD))
        dim(f"Email: {lead['email']}")

        # Generate
        info("Generating email with Groq Llama 3.1...")
        try:
            subject, body = generate_email(lead, language, cfg["groq_api_key"])
        except Exception as e:
            error(f"Generation failed: {e}")
            db.log_sent(conn, lead["id"], lead["name"], lead["email"], "", "", language, "failed")
            failed_count += 1
            continue

        # Preview
        divider()
        print(c(f"  Subject: {subject}", WHITE))
        print()
        for line in textwrap.wrap(body, width=70):
            dim(line)
        divider()

        if not auto:
            # Approve / regenerate / skip loop
            while True:
                choice = input(c(
                    "  [s]end  [r]egenerate  [k]skip  [q]quit → ", CYAN
                )).strip().lower()

                if choice == "s":
                    break
                elif choice == "r":
                    info("Regenerating...")
                    try:
                        subject, body = generate_email(lead, language, cfg["groq_api_key"])
                    except Exception as e:
                        error(f"Generation failed: {e}")
                        break
                    divider()
                    print(c(f"  Subject: {subject}", WHITE))
                    print()
                    for line in textwrap.wrap(body, width=70):
                        dim(line)
                    divider()
                elif choice == "k":
                    warn("Skipped.")
                    break
                elif choice == "q":
                    info("Stopped. Progress saved.")
                    sys.exit(0)
                else:
                    warn("Enter s / r / k / q")
            if choice in ("k", "r"):
                continue
        else:
            choice = "s"

        # Pick sender via rotation
        try:
            sender_user, sender_pwd = get_next_sender(conn)
        except NoSendersAvailable as e:
            error(f"No sender available: {e}")
            break

        # Send
        html = build_html(body, lead["name"], sender_user)
        try:
            send_email(lead["email"], subject, html, sender_user, sender_pwd)
            db.log_sent(conn, lead["id"], lead["name"], lead["email"],
                        subject, body, language, "sent", sender_user)
            success(f"[{sender_user}] Sent → {lead['email']}")
            sent_count += 1
            # Schedule follow-ups
            delays_cfg = db.get_config(conn, "followup_delays", "3,7,14")
            delays = [int(d.strip()) for d in delays_cfg.split(",")][:3]
            db.schedule_followups(conn, lead["id"], lead["name"], lead["email"], language, delays)
            dim(f"Follow-ups scheduled: +{delays[0]}d, +{delays[1]}d, +{delays[2]}d")
        except Exception as e:
            error(f"Send failed: {e}")
            db.log_sent(conn, lead["id"], lead["name"], lead["email"],
                        subject, body, language, "failed", sender_user)
            failed_count += 1

        if i < len(pending) - 1:
            dim(f"Waiting {delay_secs}s...")
            time.sleep(delay_secs)

    divider()
    success(f"Session complete — Sent: {sent_count}  Failed: {failed_count}")


def cmd_leads(args, conn):
    """List all leads."""
    header()
    leads = db.get_leads(conn)
    if not leads:
        warn("No leads yet. Run:  autoreach find")
        return

    print(c(f"  {'#':<5} {'Name':<35} {'Email':<30} {'Status'}", BOLD + WHITE))
    divider()
    for l in leads:
        email_col = c(l["email"][:28], GREEN) if l["email"] else c("no email", DIM)
        print(f"  {str(l['id']):<5} {l['name'][:33]:<35} {email_col:<30} {l['status']}")
    divider()
    dim(f"Total: {len(leads)} leads")


def cmd_stats(args, conn):
    """Show analytics."""
    header()
    a = db.get_analytics(conn)
    print(c("  Analytics", BOLD))
    divider()
    print(f"  Total leads      {c(str(a['total_leads']),  WHITE)}")
    print(f"  Leads w/ email   {c(str(a['with_email']),   CYAN)}")
    print(f"  Emails sent      {c(str(a['total_sent']),   GREEN)}")
    print(f"  Failed           {c(str(a['total_failed']), RED)}")
    print(f"  Sent today       {c(str(a['sent_today']),   YELLOW)}")
    divider()

    capacity = get_all_sender_capacity(conn)
    if capacity:
        print(c("  Sender Accounts (today)", BOLD))
        divider()
        for s in capacity:
            status_c = GREEN if s["enabled"] else DIM
            rem_c    = GREEN if s["remaining"] > 0 else RED
            print(
                f"  {s['email'][:40]:<42} "
                f"sent {c(str(s['sent_today']), YELLOW):>3}  "
                f"left {c(str(s['remaining']), rem_c):>3} / {s['daily_limit']}  "
                f"{c('on' if s['enabled'] else 'off', status_c)}"
            )
        divider()
        dim(f"Total remaining today: {total_remaining_today(conn)}")


def cmd_export(args, conn):
    """Export leads to CSV."""
    path = args.output or "autoreach_leads_export.csv"
    db.export_leads_csv(conn, path)
    success(f"Exported to {path}")


def cmd_followup(args, conn):
    """Run due follow-ups (check replies + send scheduled follow-ups)."""
    header()
    cfg = require_config(conn, "groq_api_key", "gmail_user", "gmail_app_password")

    fa = db.get_followup_analytics(conn)
    info(f"Follow-up queue — Pending: {fa['pending']}  Sent: {fa['sent']}  Replied: {fa['replied']}")
    divider()

    if fa["pending"] == 0:
        warn("No follow-ups due right now.")
        info("Follow-ups are scheduled automatically when you run:  autoreach send")
        return

    def progress(msg):
        info(msg)

    def confirm(row, subj, body):
        print()
        print(c(f"  Follow-up #{row['sequence_num']} → {row['business_name']}", BOLD))
        print(c(f"  Scheduled: {row['scheduled_for']}  ·  Email: {row['email']}", DIM))
        divider()
        print(c(f"  Subject: {subj}", WHITE))
        print()
        for line in textwrap.wrap(body, width=70):
            dim(line)
        divider()
        while True:
            choice = input(c("  [s]end  [r]egenerate  [k]skip  [q]quit → ", CYAN)).strip().lower()
            if choice in ("s", "r", "k", "q"):
                if choice == "q":
                    info("Stopped.")
                    sys.exit(0)
                return choice
            warn("Enter s / r / k / q")

    counts = run_due_followups(
        conn, cfg,
        auto=args.auto,
        progress_cb=progress,
        confirm_cb=None if args.auto else confirm,
    )

    divider()
    success(
        f"Done — Sent: {counts['sent']}  Skipped: {counts['skipped']}  "
        f"Failed: {counts['failed']}  New replies detected: {counts['replies_found']}"
    )


def cmd_replies(args, conn):
    """Check Gmail inbox for replies from leads."""
    header()
    cfg = require_config(conn, "gmail_user", "gmail_app_password")
    info("Connecting to Gmail IMAP…")
    from autoreach_core.followup import check_for_replies
    try:
        n = check_for_replies(conn, cfg["gmail_user"], cfg["gmail_app_password"],
                              progress_cb=lambda m: info(m))
        divider()
        if n:
            success(f"{n} new reply(ies) detected — follow-ups cancelled for those leads.")
        else:
            info("No new replies found.")
    except Exception as e:
        error(f"IMAP error: {e}")


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="autoreach",
        description=c("AutoReach — AI-powered cold email outreach", CYAN),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f"""
  {CYAN}Examples:{RESET}
    autoreach config                  # set API keys
    autoreach accounts list           # show sender accounts + capacity
    autoreach accounts add            # add a Gmail account (interactive)
    autoreach accounts add --email x@gmail.com --password xxxx --limit 150
    autoreach accounts disable --id 2 # pause an account
    autoreach find --city Athens --type restaurants
    autoreach scrape                  # scrape emails from websites
    autoreach send                    # preview & send (interactive)
    autoreach send --auto             # send without prompts
    autoreach send --language greek   # send in Greek
    autoreach followup                # send due follow-ups (interactive)
    autoreach followup --auto         # send due follow-ups automatically
    autoreach replies                 # check Gmail for replies
    autoreach leads                   # list all leads
    autoreach stats                   # show analytics + per-account breakdown
    autoreach export --output my_leads.csv
        """)
    )

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("config",  help="Set API keys and settings")

    # ── Accounts ─────────────────────────────────────────────────────────
    p_acct = sub.add_parser("accounts", help="Manage sender accounts for rotation")
    acct_sub = p_acct.add_subparsers(dest="accounts_cmd")

    acct_sub.add_parser("list", help="List all sender accounts and daily capacity")

    p_add = acct_sub.add_parser("add", help="Add a sender account")
    p_add.add_argument("--email",    help="Gmail address")
    p_add.add_argument("--password", help="Gmail App Password")
    p_add.add_argument("--limit",    type=int, default=150, help="Daily send limit (default: 150)")
    p_add.add_argument("--notes",    default="",            help="Optional label/notes")

    p_rem = acct_sub.add_parser("remove", help="Remove a sender account by id")
    p_rem.add_argument("--id", type=int, required=True)

    p_en = acct_sub.add_parser("enable", help="Enable a sender account")
    p_en.add_argument("--id", type=int, required=True)

    p_dis = acct_sub.add_parser("disable", help="Disable a sender account")
    p_dis.add_argument("--id", type=int, required=True)

    # ── Find ──────────────────────────────────────────────────────────────
    p_find = sub.add_parser("find", help="Find leads from Google Maps")
    p_find.add_argument("--city", help="City to search in")
    p_find.add_argument("--type", help="Business type (e.g. restaurants)")

    sub.add_parser("scrape", help="Scrape emails from lead websites")

    p_send = sub.add_parser("send", help="Generate, preview & send emails")
    p_send.add_argument("--language", choices=["english", "greek"], default="english")
    p_send.add_argument("--auto",     action="store_true", help="Skip preview prompts")

    p_fu = sub.add_parser("followup", help="Send due follow-up emails")
    p_fu.add_argument("--auto", action="store_true", help="Skip preview prompts")

    sub.add_parser("replies", help="Check Gmail inbox for replies from leads")
    sub.add_parser("leads",   help="List all leads")
    sub.add_parser("stats",   help="Show analytics")

    p_exp = sub.add_parser("export", help="Export leads to CSV")
    p_exp.add_argument("--output", default="autoreach_leads_export.csv")

    args = parser.parse_args()

    if not args.cmd:
        header()
        parser.print_help()
        sys.exit(0)

    conn = db.get_conn()

    dispatch = {
        "config":   cmd_config,
        "accounts": cmd_accounts,
        "find":     cmd_find,
        "scrape":   cmd_scrape,
        "send":     cmd_send,
        "followup": cmd_followup,
        "replies":  cmd_replies,
        "leads":    cmd_leads,
        "stats":    cmd_stats,
        "export":   cmd_export,
    }
    dispatch[args.cmd](args, conn)


if __name__ == "__main__":
    main()

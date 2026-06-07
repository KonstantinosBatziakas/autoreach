"""
Follow-up sequence engine.

Responsibilities:
  1. check_for_replies()   — check DB for leads already marked as replied
  2. run_due_followups()   — send any follow-ups whose date has arrived
  3. generate_followup_email() — AI-written follow-up, aware it's a follow-up

Reply detection no longer uses Gmail IMAP.  Replies are recorded in the
DB when a lead emails back and the user (or the web app) marks them as
replied, or via the unsubscribe link.  The desktop/CLI user can manually
mark a lead replied from the Leads tab.
"""

import time
from datetime import datetime

from autoreach_core import db
from autoreach_core.emailer import generate_email as _gen_initial, build_html, send_email
from autoreach_core.rotation import get_next_sender, NoSendersAvailable

# Default follow-up schedule (days after initial send)
DEFAULT_DELAYS = [3, 7, 14]
MAX_FOLLOWUPS  = 3


# ── Reply detection ────────────────────────────────────────────────────────

def check_for_replies(conn, progress_cb=None) -> int:
    """
    Check the local DB for leads whose status is 'replied' but whose
    pending follow-ups have not yet been marked as replied/skipped.

    This replaces the old Gmail IMAP scan.  Any reply recorded in the DB
    (e.g. by the user clicking "Mark Replied" or via the web app) will be
    picked up here and used to skip overdue follow-ups.

    Returns the number of leads newly detected as having replied.
    """
    if progress_cb:
        progress_cb("Checking database for replied leads…")

    leads = db.get_leads(conn, with_email_only=True)
    found = 0
    for row in leads:
        if row["status"] == "replied":
            if not db.has_replied(conn, row["id"]):
                db.mark_lead_replied(conn, row["id"], row["email"])
                found += 1
                if progress_cb:
                    progress_cb(f"↩ Marked {row['email']} as replied.")

    if progress_cb and not found:
        progress_cb("No new replies found in database.")
    return found


# ── Follow-up email generation ─────────────────────────────────────────────

def generate_followup_email(business: dict, sequence_num: int,
                             language: str, groq_api_key: str) -> tuple[str, str]:
    """
    Returns (subject, body) for a follow-up.
    sequence_num: 1 = first follow-up, 2 = second, 3 = third (last chance).
    """
    from groq import Groq
    client = Groq(api_key=groq_api_key)
    name    = business.get("name", "")
    address = business.get("address", "")

    tone_map = {
        1: "a gentle, friendly follow-up",
        2: "a slightly more direct follow-up",
        3: "a final, brief follow-up — mention this is the last you'll reach out",
    }
    tone = tone_map.get(sequence_num, "a follow-up")

    if language.lower() == "greek":
        prompt = (
            f"Γράψε {tone} email στα ελληνικά για την επιχείρηση '{name}' ({address}). "
            f"Αναφέρου ότι έστειλες ένα προηγούμενο email αλλά δεν έλαβες απάντηση. "
            f"Κανόνες που ΠΡΕΠΕΙ να ακολουθήσεις:\n"
            f"- Απευθύνσου στην επιχείρηση ονομαστικά ('{name}')\n"
            f"- Γράψε σαν άτομο, πρώτο πρόσωπο\n"
            f"- ΜΗΝ αφήνεις placeholders όπως [Όνομα], [Εταιρεία] κ.λπ.\n"
            f"- Υπόγραψε ως 'Κωνσταντίνος'\n"
            f"- Κάτω από 100 λέξεις\n"
            f"- Μόνο το κείμενο, χωρίς θέμα, χωρίς εξηγήσεις"
        )
        subject_map = {
            1: f"Re: Μια ιδέα για {name}",
            2: f"Τελευταία επικοινωνία — {name}",
            3: f"Τελευταίο μήνυμα για {name}",
        }
    else:
        prompt = (
            f"Write {tone} email to '{name}' ({address}). "
            f"Reference that you sent a previous email but haven't heard back. "
            f"Rules you MUST follow:\n"
            f"- Address the business by name ('{name}')\n"
            f"- Write as a person, first person (I/my)\n"
            f"- Do NOT leave any placeholders like [Name], [Company] etc.\n"
            f"- Sign off as 'Konstantinos'\n"
            f"- Under 100 words\n"
            f"- Return only the email body, no subject line, no explanations"
        )
        subject_map = {
            1: f"Following up — {name}",
            2: f"Still interested? — {name}",
            3: f"Last message for {name}",
        }

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    body    = response.choices[0].message.content.strip()
    subject = subject_map.get(sequence_num, f"Follow-up — {name}")
    return subject, body


# ── Main runner ────────────────────────────────────────────────────────────

def run_due_followups(conn, cfg: dict, auto: bool = True,
                      progress_cb=None, confirm_cb=None) -> dict:
    """
    Check for replies first, then send all due follow-ups.

    cfg must contain:
      groq_api_key   — Groq API key for email generation
      resend_api_key — Resend API key for sending
      from_email     — sender address (optional, defaults to onboarding@resend.dev)

    progress_cb(message: str)              — status updates
    confirm_cb(followup_row, subj, body)   — for interactive mode;
        should return 's' send / 'r' regen / 'k' skip

    Returns dict with sent/skipped/failed counts.
    """
    counts = {"sent": 0, "skipped": 0, "failed": 0, "replies_found": 0}

    # 1. Check for replies first (DB-based, no IMAP needed)
    if progress_cb:
        progress_cb("Checking database for replied leads…")
    try:
        new_replies = check_for_replies(conn, progress_cb=progress_cb)
        counts["replies_found"] = new_replies
        if progress_cb and new_replies:
            progress_cb(f"✓ {new_replies} new reply(ies) detected — follow-ups cancelled for those leads.")
    except Exception as e:
        if progress_cb:
            progress_cb(f"⚠ Reply check failed (skipping): {e}")

    # 2. Get due follow-ups
    due = db.get_due_followups(conn)
    if not due:
        if progress_cb:
            progress_cb("No follow-ups due today.")
        return counts

    if progress_cb:
        progress_cb(f"{len(due)} follow-up(s) due.")

    delay_secs = int(cfg.get("delay_seconds", "8"))

    for i, row in enumerate(due):
        lead = {"name": row["business_name"], "address": row.get("address", ""),
                "id": row["lead_id"], "email": row["email"]}

        # Double-check: skip if lead has since replied
        if db.has_replied(conn, row["lead_id"]):
            db.mark_followup_skipped(conn, row["id"])
            counts["skipped"] += 1
            if progress_cb:
                progress_cb(f"Skip {lead['name']} — already replied.")
            continue

        # Generate
        if progress_cb:
            progress_cb(f"[{i+1}/{len(due)}] Generating follow-up #{row['sequence_num']} for {lead['name']}…")
        try:
            subj, body = generate_followup_email(
                lead, row["sequence_num"], row["language"], cfg["groq_api_key"]
            )
        except Exception as e:
            if progress_cb:
                progress_cb(f"✗ Generation failed: {e}")
            counts["failed"] += 1
            continue

        # Interactive confirm
        action = "s"
        if not auto and confirm_cb:
            action = confirm_cb(row, subj, body)

        if action == "k":
            db.mark_followup_skipped(conn, row["id"])
            counts["skipped"] += 1
            if progress_cb:
                progress_cb(f"Skipped {lead['name']}.")
            continue

        if action == "r":
            # Regenerate once more
            try:
                subj, body = generate_followup_email(
                    lead, row["sequence_num"], row["language"], cfg["groq_api_key"]
                )
            except Exception as e:
                if progress_cb:
                    progress_cb(f"✗ Regen failed: {e}")
                counts["failed"] += 1
                continue

        # Get Resend credentials
        try:
            resend_key, from_email = get_next_sender(conn)
        except NoSendersAvailable as e:
            if progress_cb:
                progress_cb(f"✗ No sender configured: {e}")
            counts["failed"] += 1
            continue

        # Send via Resend
        html = build_html(body, lead["name"], row["email"])
        try:
            send_email(row["email"], subj, html, resend_key, from_email)
            db.mark_followup_sent(conn, row["id"], subj, body)
            # Log to sent_log so daily counts are accurate
            db.log_sent(conn, lead["id"], lead["name"], row["email"],
                        subj, body, row["language"], "sent", from_email)
            counts["sent"] += 1
            if progress_cb:
                progress_cb(f"✓ [{from_email}] Sent follow-up #{row['sequence_num']} → {row['email']}")
        except Exception as e:
            counts["failed"] += 1
            if progress_cb:
                progress_cb(f"✗ Send failed: {e}")

        if i < len(due) - 1:
            time.sleep(delay_secs)

    return counts

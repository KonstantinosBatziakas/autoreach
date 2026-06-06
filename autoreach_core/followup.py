"""
Follow-up sequence engine.

Responsibilities:
  1. check_for_replies()   — poll Gmail via IMAP, mark replied leads
  2. run_due_followups()   — send any follow-ups whose date has arrived
  3. generate_followup_email() — AI-written follow-up, aware it's a follow-up
"""

import imaplib
import email as email_lib
import time
from datetime import datetime

from autoreach_core import db
from autoreach_core.emailer import generate_email as _gen_initial, build_html, send_email
from autoreach_core.rotation import get_next_sender, NoSendersAvailable

# Default follow-up schedule (days after initial send)
DEFAULT_DELAYS = [3, 7, 14]
MAX_FOLLOWUPS  = 3


# ── Reply detection ────────────────────────────────────────────────────────

def _scan_inbox_for_replies(gmail_user: str, gmail_app_password: str,
                             lead_map: dict, progress_cb=None) -> tuple[int, dict]:
    """
    Scan a single Gmail inbox for replies from leads in lead_map.
    Returns (replies_found, remaining_lead_map) so callers can chain
    across multiple inboxes.
    """
    if progress_cb:
        progress_cb(f"Connecting to Gmail IMAP as {gmail_user}…")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_user, gmail_app_password)
        mail.select("inbox")
    except Exception as e:
        if progress_cb:
            progress_cb(f"⚠ IMAP login failed for {gmail_user}: {e}")
        return 0, lead_map

    found = 0
    try:
        # Only search last 60 days — avoids scanning entire inbox history
        since_date = (datetime.now().replace(day=1) - __import__('datetime').timedelta(days=60)).strftime("%d-%b-%Y")
        _, data = mail.search(None, f'(SINCE "{since_date}")')
        msg_ids = data[0].split()

        if not msg_ids:
            return 0, lead_map

        if progress_cb:
            progress_cb(f"  Scanning {len(msg_ids)} recent message(s)…")

        # Batch-fetch all headers in one IMAP round trip
        id_range = ",".join(m.decode() for m in msg_ids)
        _, fetch_data = mail.fetch(id_range, "(BODY[HEADER.FIELDS (FROM SUBJECT)])")

        for item in fetch_data:
            if not lead_map:
                break
            if not isinstance(item, tuple):
                continue
            try:
                raw = item[1].decode("utf-8", errors="ignore")
                parsed = email_lib.message_from_string(raw)
                from_header    = parsed.get("From", "").lower()
                subject_header = parsed.get("Subject", "").strip().lower()

                sender_addr = from_header
                if "<" in from_header:
                    sender_addr = from_header.split("<")[1].rstrip(">").strip()

                if sender_addr in lead_map:
                    lead_id, conn = lead_map[sender_addr]
                    is_unsub = "unsubscribe" in subject_header

                    db.mark_lead_replied(conn, lead_id, sender_addr)
                    if is_unsub:
                        conn.execute(
                            "UPDATE leads SET status='unsubscribed' WHERE id=?", (lead_id,)
                        )
                        conn.commit()
                        if progress_cb:
                            progress_cb(f"🚫 Unsubscribed: {sender_addr}")
                    else:
                        if progress_cb:
                            progress_cb(f"↩ Reply from {sender_addr}")

                    found += 1
                    del lead_map[sender_addr]

            except Exception:
                continue

    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return found, lead_map


def check_for_replies(conn, gmail_user: str, gmail_app_password: str,
                      progress_cb=None) -> int:
    """
    Scan Gmail inboxes for replies from known leads and mark them.

    Checks ALL enabled sender accounts (not just the one passed as args)
    so replies sent to any rotation account are detected.  Falls back
    gracefully to checking only gmail_user if no accounts table exists.

    Returns the total number of new replies detected.
    """
    leads = db.get_leads(conn, with_email_only=True)
    # lead_map: {lead_email_lower: (lead_id, conn)}
    lead_map = {
        row["email"].lower(): (row["id"], conn)
        for row in leads
        if not db.has_replied(conn, row["id"])
    }

    if not lead_map:
        return 0

    # Build list of (user, password) pairs to poll
    accounts_to_poll: list[tuple[str, str]] = []
    accts = db.get_enabled_sender_accounts(conn)
    if accts:
        for acct in accts:
            accounts_to_poll.append((acct["email"], acct["app_password"]))
    else:
        # Legacy single-account fallback
        accounts_to_poll = [(gmail_user, gmail_app_password)]

    total_found = 0
    for user, pwd in accounts_to_poll:
        if not lead_map:
            break
        n, lead_map = _scan_inbox_for_replies(user, pwd, lead_map, progress_cb)
        total_found += n

    return total_found


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

    progress_cb(message: str)              — status updates
    confirm_cb(followup_row, subj, body)   — for interactive mode;
        should return 's' send / 'r' regen / 'k' skip

    Returns dict with sent/skipped/failed counts.
    """
    counts = {"sent": 0, "skipped": 0, "failed": 0, "replies_found": 0}

    # 1. Check for replies first
    if progress_cb:
        progress_cb("Checking Gmail inbox for replies…")
    try:
        new_replies = check_for_replies(
            conn,
            cfg["gmail_user"],
            cfg["gmail_app_password"],
            progress_cb=progress_cb,
        )
        counts["replies_found"] = new_replies
        if progress_cb and new_replies:
            progress_cb(f"✓ {new_replies} new reply(ies) detected — follow-ups cancelled for those leads.")
    except Exception as e:
        if progress_cb:
            progress_cb(f"⚠ IMAP check failed (skipping reply detection): {e}")

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

        # Pick sender via rotation
        try:
            sender_user, sender_pwd = get_next_sender(conn)
        except NoSendersAvailable as e:
            if progress_cb:
                progress_cb(f"✗ No senders available: {e}")
            counts["failed"] += 1
            continue

        # Send
        html = build_html(body, lead["name"], sender_user)
        try:
            send_email(row["email"], subj, html, sender_user, sender_pwd)
            db.mark_followup_sent(conn, row["id"], subj, body)
            # Log to sent_log so rotation counts are accurate
            db.log_sent(conn, lead["id"], lead["name"], row["email"],
                        subj, body, row["language"], "sent", sender_user)
            counts["sent"] += 1
            if progress_cb:
                progress_cb(f"✓ [{sender_user}] Sent follow-up #{row['sequence_num']} → {row['email']}")
        except Exception as e:
            counts["failed"] += 1
            if progress_cb:
                progress_cb(f"✗ Send failed: {e}")

        if i < len(due) - 1:
            time.sleep(delay_secs)

    return counts

"""
AutoReach Follow-up Email Sequences
=====================================
Sends follow-up emails at +3, +7, and +14 days after the initial outreach.
Uses Resend HTTP API (same as the main outreach flow) — avoids Render SMTP blocks.

All data is now persisted in Turso (or local SQLite fallback) via db.py.
"""

import os
import requests as _http
from datetime import datetime, timedelta

from groq import Groq
from db import get_db

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv('GROQ_API_KEY', '')
# RESEND_API_KEY and FROM_EMAIL are optional server-side overrides.
# If not set, follow-ups are skipped (user must run them manually from the web UI
# with their own Resend key passed via the outreach form).
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
FROM_EMAIL     = os.getenv('FROM_EMAIL', 'onboarding@resend.dev')
BASE_URL       = os.getenv('BASE_URL', 'https://app.autoreach.dev').rstrip('/')

# Days after initial email to send each follow-up
FOLLOWUP_SCHEDULE = [3, 7, 14]

groq_client = None

# ── DB helpers ────────────────────────────────────────────────────────────────

def _read_sent_log():
    """Returns list of dicts from sent_log table."""
    db = get_db()
    rows = db.execute('SELECT * FROM sent_log ORDER BY id').fetchall()
    db.close()
    return [dict(row) for row in rows]

def _read_followup_log():
    """Returns list of dicts from followup_log table."""
    db = get_db()
    rows = db.execute('SELECT * FROM followup_log ORDER BY id').fetchall()
    db.close()
    return [dict(row) for row in rows]

def _log_followup(business_name, email, original_date_sent, step, subject, body):
    db = get_db()
    db.execute(
        'INSERT INTO followup_log (business_name, email, original_date_sent, followup_step, date_sent, subject, body) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (
            business_name,
            email,
            original_date_sent,
            int(step),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            subject,
            body,
        )
    )
    db.commit()
    db.close()

def _steps_already_sent(email_addr):
    """Returns a set of follow-up steps already sent to this email."""
    db = get_db()
    rows = db.execute(
        'SELECT followup_step FROM followup_log WHERE LOWER(email) = LOWER(?)',
        (email_addr,)
    ).fetchall()
    db.close()
    return {int(row[0]) for row in rows}

def _is_unsubscribed(email_addr: str) -> bool:
    """Check if the lead has unsubscribed."""
    db = get_db()
    row = db.execute(
        "SELECT unsubscribed FROM businesses WHERE LOWER(email) = LOWER(?)",
        (email_addr,)
    ).fetchone()
    db.close()
    if row is None:
        return False
    return bool(row['unsubscribed'])

def _has_replied(email_addr: str) -> bool:
    """Check if the lead's stage is 'Replied' in the DB."""
    db = get_db()
    row = db.execute(
        "SELECT stage FROM businesses WHERE LOWER(email) = LOWER(?)",
        (email_addr,)
    ).fetchone()
    db.close()
    if row is None:
        return False
    return (row['stage'] or '').lower() == 'replied'

# ── Email generation ──────────────────────────────────────────────────────────

def _generate_followup(business_name: str, step: int) -> tuple[str, str]:
    """Returns (subject, body) for the given follow-up step."""
    global groq_client
    if not GROQ_API_KEY:
        raise ValueError('GROQ_API_KEY not configured — cannot generate follow-up email.')
    if not groq_client:
        groq_client = Groq(api_key=GROQ_API_KEY)

    step_context = {
        3:  "a short, friendly first follow-up (3 days after initial email). Mention you wanted to check if they had a chance to read your previous message. Keep it under 80 words.",
        7:  "a second follow-up (7 days after initial email). Add a brief value proposition — mention one specific benefit like more online visibility or new customers. Keep it under 100 words.",
        14: "a final follow-up (14 days after initial email). Keep it very short, let them know this is your last message, and leave the door open for future contact. Under 60 words.",
    }

    prompt = f"""Write a cold outreach follow-up email for a web design and digital marketing agency.
Business name: {business_name}
Follow-up context: {step_context[step]}
Return only the email body text, no subject line."""

    response = groq_client.chat.completions.create(
        model='llama-3.1-8b-instant',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    body = response.choices[0].message.content.strip()
    subjects = {
        3:  f'Following up — {business_name}',
        7:  f'One more thing for {business_name}',
        14: f'Last note — {business_name}',
    }
    return subjects[step], body

def _build_html(body: str, to_email: str = '') -> str:
    import urllib.parse
    year = datetime.now().year
    unsub_url = f"{BASE_URL}/unsubscribe?email={urllib.parse.quote(to_email)}"
    unsub_link = f'<a href="{unsub_url}" style="color:#aaa;text-decoration:underline;font-size:11px;">Unsubscribe</a>'
    body_html = body.replace('\n', '<br>')
    return (
        "<!DOCTYPE html><html><head><style>"
        "body{margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;}"
        ".wrapper{max-width:600px;margin:40px auto;background:#fff;border-radius:10px;overflow:hidden;}"
        ".header{background:#000;padding:30px 40px;}"
        ".header h1{color:#fff;margin:0;font-size:24px;letter-spacing:2px;}"
        ".header p{color:#aaa;margin:5px 0 0;font-size:13px;}"
        ".body{padding:40px;color:#333;font-size:15px;line-height:1.7;}"
        ".footer{padding:20px 40px;border-top:1px solid #eee;color:#aaa;font-size:12px;}"
        "</style></head><body><div class='wrapper'>"
        "<div class='header'><h1>AUTOREACH</h1><p>Digital Presence Services</p></div>"
        f"<div class='body'><p>{body_html}</p></div>"
        f"<div class='footer'>&copy; {year} AutoReach. All rights reserved. &nbsp;|&nbsp; {unsub_link}</div>"
        "</div></body></html>"
    )

def _send_via_resend(to_email: str, subject: str, html_body: str):
    """Send email via Resend HTTP API (avoids Render SMTP blocks)."""
    if not RESEND_API_KEY:
        raise ValueError('RESEND_API_KEY not configured — cannot send follow-up email.')
    resp = _http.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {RESEND_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'from': FROM_EMAIL,
            'to': [to_email],
            'subject': subject,
            'html': html_body,
        },
        timeout=15,
    )
    if not resp.ok:
        err = resp.json().get('message', resp.text)
        raise Exception(f'Resend error: {err}')

# ── Main entry point ──────────────────────────────────────────────────────────

def run_followups() -> dict:
    """
    Check all sent emails and send any due follow-ups.
    Returns a summary dict: {sent: int, skipped_replied: int, skipped_not_due: int, errors: int}
    """
    if not RESEND_API_KEY:
        print('[followup] RESEND_API_KEY not configured — skipping.')
        return {'sent': 0, 'skipped_replied': 0, 'skipped_not_due': 0, 'errors': 0}
    if not GROQ_API_KEY:
        print('[followup] GROQ_API_KEY not configured — skipping.')
        return {'sent': 0, 'skipped_replied': 0, 'skipped_not_due': 0, 'errors': 0}

    sent_log = _read_sent_log()
    now = datetime.now()
    summary = {'sent': 0, 'skipped_replied': 0, 'skipped_not_due': 0, 'errors': 0}

    for row in sent_log:
        email_addr    = row.get('email', '').strip()
        business_name = row.get('business_name', '').strip()
        date_sent_str = row.get('date_sent', '').strip()

        if not email_addr or not date_sent_str:
            continue

        # Skip unsubscribed leads
        if _is_unsubscribed(email_addr):
            continue

        # Skip leads who replied
        if _has_replied(email_addr):
            summary['skipped_replied'] += 1
            continue

        try:
            original_date = datetime.strptime(date_sent_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                original_date = datetime.strptime(date_sent_str[:10], '%Y-%m-%d')
            except ValueError:
                continue

        steps_sent = _steps_already_sent(email_addr)

        for step in FOLLOWUP_SCHEDULE:
            if step in steps_sent:
                continue

            due_date = original_date + timedelta(days=step)
            if now < due_date:
                summary['skipped_not_due'] += 1
                continue

            try:
                subject, body = _generate_followup(business_name, step)
                html = _build_html(body, email_addr)
                _send_via_resend(email_addr, subject, html)
                _log_followup(business_name, email_addr, date_sent_str, step, subject, body)
                print(f'[followup] Sent step {step} to {email_addr}')
                summary['sent'] += 1
            except Exception as e:
                print(f'[followup] Error sending to {email_addr}: {e}')
                summary['errors'] += 1

    return summary


def get_followup_stats() -> dict:
    """Returns stats for display in the web UI."""
    rows = _read_followup_log()
    return {
        'total_followups': len(rows),
        'step_counts': {
            3:  sum(1 for r in rows if str(r.get('followup_step')) == '3'),
            7:  sum(1 for r in rows if str(r.get('followup_step')) == '7'),
            14: sum(1 for r in rows if str(r.get('followup_step')) == '14'),
        },
        'recent': rows[-10:][::-1],  # last 10, newest first
    }

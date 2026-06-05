"""
AutoReach Follow-up Email Sequences
=====================================
Sends follow-up emails at +3, +7, +14 days after the initial outreach.
Stops if a reply is detected via IMAP.

Follow-up log columns (followup_log.csv):
  business_name, email, original_date_sent, followup_step, date_sent, subject, body

Usage:
  from followup import run_followups
  run_followups()   # checks and sends all due follow-ups
"""

import csv
import imaplib
import email as email_lib
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR         = os.getenv('DATA_DIR', '/data')
SENT_LOG_FILE    = os.path.join(DATA_DIR, 'sent_log.csv')
FOLLOWUP_LOG     = os.path.join(DATA_DIR, 'followup_log.csv')

GMAIL_USER       = os.getenv('GMAIL_USER', '')
GMAIL_PASS       = os.getenv('GMAIL_APP_PASSWORD', '')
GROQ_API_KEY     = os.getenv('GROQ_API_KEY', '')

# Days after initial email to send each follow-up
FOLLOWUP_SCHEDULE = [3, 7, 14]

groq_client = None

# ── CSV helpers ───────────────────────────────────────────────────────────────
def _ensure_followup_log():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FOLLOWUP_LOG):
        with open(FOLLOWUP_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'business_name', 'email', 'original_date_sent',
                'followup_step', 'date_sent', 'subject', 'body'
            ])
            writer.writeheader()

def _read_sent_log():
    """Returns list of dicts from sent_log.csv."""
    if not os.path.exists(SENT_LOG_FILE):
        return []
    with open(SENT_LOG_FILE, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def _read_followup_log():
    """Returns list of dicts from followup_log.csv."""
    _ensure_followup_log()
    with open(FOLLOWUP_LOG, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def _log_followup(business_name, email, original_date_sent, step, subject, body):
    _ensure_followup_log()
    with open(FOLLOWUP_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'business_name', 'email', 'original_date_sent',
            'followup_step', 'date_sent', 'subject', 'body'
        ])
        writer.writerow({
            'business_name': business_name,
            'email': email,
            'original_date_sent': original_date_sent,
            'followup_step': step,
            'date_sent': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'subject': subject,
            'body': body,
        })

def _steps_already_sent(email_addr):
    """Returns a set of follow-up steps already sent to this email."""
    rows = _read_followup_log()
    return {int(r['followup_step']) for r in rows if r['email'].lower() == email_addr.lower()}

# ── IMAP reply detection ──────────────────────────────────────────────────────
def _has_replied(to_email: str) -> bool:
    """
    Checks Gmail INBOX for any message FROM to_email.
    Returns True if a reply has been received.
    """
    if not GMAIL_USER or not GMAIL_PASS:
        return False
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select('INBOX')
        # Search for emails FROM that address
        status, data = mail.search(None, f'FROM "{to_email}"')
        mail.logout()
        if status == 'OK' and data[0]:
            return True
    except Exception as e:
        print(f'[followup] IMAP check failed for {to_email}: {e}')
    return False

# ── Email generation ──────────────────────────────────────────────────────────
def _generate_followup(business_name: str, step: int) -> tuple[str, str]:
    """Returns (subject, body) for the given follow-up step."""
    global groq_client
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

def _build_html(body: str) -> str:
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
        f"<div class='body'><p>{body}</p></div>"
        "<div class='footer'>&copy; 2025 AutoReach. All rights reserved.</div>"
        "</div></body></html>"
    )

def _send_email(to_email: str, subject: str, html_body: str):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg.attach(MIMEText(html_body, 'html'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

# ── Main entry point ──────────────────────────────────────────────────────────
def run_followups() -> dict:
    """
    Check all sent emails and send any due follow-ups.
    Returns a summary dict: {sent: int, skipped_replied: int, skipped_not_due: int, errors: int}
    """
    if not GMAIL_USER or not GMAIL_PASS:
        print('[followup] Gmail credentials not configured — skipping.')
        return {'sent': 0, 'skipped_replied': 0, 'skipped_not_due': 0, 'errors': 0}

    sent_log = _read_sent_log()
    now = datetime.now()
    summary = {'sent': 0, 'skipped_replied': 0, 'skipped_not_due': 0, 'errors': 0}

    for row in sent_log:
        email_addr     = row.get('email', '').strip()
        business_name  = row.get('business_name', '').strip()
        date_sent_str  = row.get('date_sent', '').strip()

        if not email_addr or not date_sent_str:
            continue

        try:
            original_date = datetime.strptime(date_sent_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue

        steps_sent = _steps_already_sent(email_addr)

        for step in FOLLOWUP_SCHEDULE:
            if step in steps_sent:
                continue  # already sent this step

            due_date = original_date + timedelta(days=step)
            if now < due_date:
                summary['skipped_not_due'] += 1
                continue  # not due yet

            # Check for reply before sending
            if _has_replied(email_addr):
                print(f'[followup] {email_addr} replied — stopping sequence.')
                summary['skipped_replied'] += 1
                break  # stop all further follow-ups for this lead

            try:
                subject, body = _generate_followup(business_name, step)
                html = _build_html(body)
                _send_email(email_addr, subject, html)
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
            3:  sum(1 for r in rows if r.get('followup_step') == '3'),
            7:  sum(1 for r in rows if r.get('followup_step') == '7'),
            14: sum(1 for r in rows if r.get('followup_step') == '14'),
        },
        'recent': rows[-10:][::-1],  # last 10, newest first
    }

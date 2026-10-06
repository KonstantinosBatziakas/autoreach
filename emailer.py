"""
Legacy standalone emailer — used by the root-level scripts only.
Sends email via the Resend HTTP API.
"""
import os
from groq import Groq
from datetime import datetime
from db import get_db
from moderation.delivery import DeliveryBlocked, DeliveryQueued, send_moderated
from moderation.service import moderate_and_queue

groq_client = None  # initialized lazily on first use
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "onboarding@resend.dev")


def get_sent_emails():
    """Returns a set of lowercase email addresses already sent to."""
    db = get_db()
    rows = db.execute('SELECT email FROM sent_log').fetchall()
    db.close()
    return {row[0].lower() for row in rows}


def log_sent_email(business_name, email, subject, body):
    db = get_db()
    db.execute(
        'INSERT INTO sent_log (business_name, email, date_sent, subject, body) VALUES (?, ?, ?, ?, ?)',
        (business_name, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), subject, body)
    )
    db.commit()
    db.close()


def _load_custom_template():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = 'email_template'").fetchone()
    db.close()
    if row and row[0]:
        return row[0].strip()
    return None


def generate_email(business, language="english"):
    global groq_client
    if groq_client is None:
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    custom_template = _load_custom_template()

    if custom_template:
        filled = custom_template.format(
            name=business.get('name', ''),
            address=business.get('address', ''),
            sender_name=os.getenv('SENDER_NAME', 'AutoReach Team'),
        )
        prompt = (
            f"Here is an email template already filled in for a business called {business['name']}:\n\n"
            f"{filled}\n\n"
            f"Lightly personalise this email to feel less generic. Keep the same structure and length. "
            f"Return only the final email body, no subject line."
        )
    elif language.lower() == "greek":
        prompt = (
            f"Γράψε ένα σύντομο επαγγελματικό email για cold outreach προσφέροντας υπηρεσίες "
            f"σχεδιασμού ιστοσελίδων και ψηφιακού μάρκετινγκ στην επιχείρηση {business['name']} "
            f"που βρίσκεται στη διεύθυνση {business['address']}. "
            f"Κάτω από 150 λέξεις. Επέστρεψε μόνο το κείμενο του email."
        )
    else:
        prompt = (
            f"Write a short professional cold outreach email offering web design and digital marketing "
            f"services to {business['name']} located at {business['address']}. "
            f"Under 150 words. Only return the email body."
        )

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}]
    )
    body = response.choices[0].message.content.strip()
    conn = get_db()
    try:
        decision, queue_id = moderate_and_queue(
            body, 0, 'generate', 'email', conn,
            payload={'business_name': business.get('name', ''), 'email': business.get('email', ''),
                     'body': body}, api_key=os.getenv('GROQ_API_KEY'),
        )
    finally:
        conn.close()
    if decision.verdict == 'block':
        raise DeliveryBlocked(decision)
    if decision.verdict == 'review':
        raise DeliveryQueued(queue_id or '', decision)
    return body


def build_html(body):
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
        "<div class='body'><p>Dear Sir/Madam,</p><p>" + body + "</p>"
        "<p>Best regards,<br><strong>AutoReach Team</strong></p></div>"
        "<div class='footer'>&copy; 2025 AutoReach. All rights reserved.</div>"
        "</div></body></html>"
    )


def send_email(to_email, subject, html_body,
               resend_api_key=None, from_email=None):
    """Send via the Resend HTTP API."""
    key  = resend_api_key or RESEND_API_KEY
    frm  = from_email or FROM_EMAIL or "onboarding@resend.dev"
    if not key:
        raise RuntimeError(
            "RESEND_API_KEY environment variable is not set. "
            "Add it to your .env file or environment."
        )
    from html.parser import HTMLParser
    class _Text(HTMLParser):
        def __init__(self): super().__init__(); self.parts=[]
        def handle_data(self, data): self.parts.append(data)
    parser = _Text(); parser.feed(html_body)
    conn = get_db()
    try:
        send_moderated({
            'email': to_email, 'subject': subject, 'body': ' '.join(parser.parts),
            'html': html_body, 'resend_api_key': key, 'from_email': frm,
        }, 0, conn, api_key=os.getenv('GROQ_API_KEY'))
    finally:
        conn.close()
    print(f"Email sent to {to_email}")


def run_outreach(auto_send=False):
    sent_emails = get_sent_emails()
    db = get_db()
    businesses = [dict(row) for row in db.execute('SELECT * FROM businesses ORDER BY id').fetchall()]
    db.close()

    for business in businesses:
        if not business.get("email"):
            print(f"Skipping {business['name']} - no email.")
            continue

        if business["email"].lower() in sent_emails:
            print(f"Skipping {business['name']} - already sent to {business['email']}")
            continue

        if not auto_send:
            lang_choice = input("\nSend in English or Greek? (e/g): ").strip().lower()
            language = "greek" if lang_choice == "g" else "english"
        else:
            language = "english"

        body = generate_email(business, language)
        html = build_html(body)
        subject = (
            f"Quick question for {business['name']}"
            if language == "english"
            else f"Γρήγορη ερώτηση για {business['name']}"
        )

        print(f"\nBusiness: {business['name']}")
        print(f"Email: {business['email']}")
        print(f"Language: {language}")
        print(f"Body:\n{body}")

        if not auto_send:
            confirm = input("\nSend this email? (y/n): ").strip().lower()
        else:
            confirm = "y"

        if confirm == "y":
            send_email(business["email"], subject, html)
            log_sent_email(business["name"], business["email"], subject, body)
        else:
            print("Skipped.")


if __name__ == "__main__":
    run_outreach()

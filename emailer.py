import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime
from db import get_db

load_dotenv()

groq_client = None  # initialized lazily on first use
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")

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
        prompt = f"Γράψε ένα σύντομο επαγγελματικό email για cold outreach προσφέροντας υπηρεσίες σχεδιασμού ιστοσελίδων και ψηφιακού μάρκετινγκ στην επιχείρηση {business['name']} που βρίσκεται στη διεύθυνση {business['address']}. Κάτω από 150 λέξεις. Επέστρεψε μόνο το κείμενο του email."
    else:
        prompt = f"Write a short professional cold outreach email offering web design and digital marketing services to {business['name']} located at {business['address']}. Under 150 words. Only return the email body."

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def build_html(body):
    return "<!DOCTYPE html><html><head><style>body{margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;}.wrapper{max-width:600px;margin:40px auto;background:#fff;border-radius:10px;overflow:hidden;}.header{background:#000;padding:30px 40px;}.header h1{color:#fff;margin:0;font-size:24px;letter-spacing:2px;}.header p{color:#aaa;margin:5px 0 0;font-size:13px;}.body{padding:40px;color:#333;font-size:15px;line-height:1.7;}.footer{padding:20px 40px;border-top:1px solid #eee;color:#aaa;font-size:12px;}</style></head><body><div class='wrapper'><div class='header'><h1>AUTOREACH</h1><p>Digital Presence Services</p></div><div class='body'><p>Dear Sir/Madam,</p><p>" + body + "</p><p>Best regards,<br><strong>AutoReach Team</strong></p></div><div class='footer'>&copy; 2025 AutoReach. All rights reserved.</div></div></body></html>"

def send_email(to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
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
        subject = f"Quick question for {business['name']}" if language == "english" else f"Γρήγορη ερώτηση για {business['name']}"

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

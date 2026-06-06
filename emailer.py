import smtplib
import csv
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

groq_client = None  # initialized lazily on first use
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
SENT_LOG_FILE = "sent_log.csv"

def initialize_sent_log():
    if not os.path.exists(SENT_LOG_FILE):
        with open(SENT_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["business_name", "email", "date_sent", "subject", "body"])
            writer.writeheader()

def get_sent_emails():
    initialize_sent_log()
    sent = set()
    with open(SENT_LOG_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sent.add(row["email"].lower())
    return sent

def log_sent_email(business_name, email, subject, body):
    initialize_sent_log()
    with open(SENT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["business_name", "email", "date_sent", "subject", "body"])
        writer.writerow({
            "business_name": business_name,
            "email": email,
            "date_sent": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subject": subject,
            "body": body
        })

def _load_custom_template():
    data_dir = os.getenv('DATA_DIR', '/data')
    template_file = os.path.join(data_dir, 'email_template.txt')
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

def generate_email(business, language="english"):
    global groq_client
    if groq_client is None:
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    custom_template = _load_custom_template()

    if custom_template:
        # Fill placeholders then ask Groq to lightly personalise
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
        model="llama-3.3-70b-versatile",
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

def run_outreach(csv_file="businesses.csv", auto_send=False):
    sent_emails = get_sent_emails()
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for business in reader:
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
"""
Email generation + sending with rate limiting and unsubscribe footer.
"""
import smtplib
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq

# Rate limit: max N emails per session, with a delay between each
MAX_PER_RUN   = 50
DELAY_BETWEEN = 8  # seconds between sends (avoids spam flags)


def generate_email(business: dict, language: str, groq_api_key: str) -> tuple[str, str]:
    """Returns (subject, body_text)"""
    client = Groq(api_key=groq_api_key)
    name = business.get("name", "")
    address = business.get("address", "")

    if language.lower() == "greek":
        prompt = (
            f"Γράψε ένα σύντομο, φυσικό cold outreach email στα ελληνικά "
            f"προς την επιχείρηση '{name}' (διεύθυνση: {address}). "
            f"Είσαι freelancer που προσφέρει υπηρεσίες web design και ψηφιακού μάρκετινγκ. "
            f"Κανόνες που ΠΡΕΠΕΙ να ακολουθήσεις:\n"
            f"- Απευθύνσου στην επιχείρηση ονομαστικά ('{name}') στην αρχή\n"
            f"- Γράψε σαν άτομο, όχι εταιρεία — χρησιμοποίησε πρώτο πρόσωπο (εγώ/μου)\n"
            f"- ΜΗΝ αφήνεις placeholders όπως [Όνομα], [Εταιρεία], [Τίτλος] κ.λπ.\n"
            f"- Υπόγραψε ως 'Κωνσταντίνος' στο τέλος\n"
            f"- Κάτω από 120 λέξεις\n"
            f"- Επέστρεψε ΜΟΝΟ το κείμενο του email, χωρίς θέμα, χωρίς εξηγήσεις"
        )
        subject = f"Μια ιδέα για {name}"
    else:
        prompt = (
            f"Write a short, natural cold outreach email to '{name}' "
            f"located at {address}. You are a freelancer offering web design and digital marketing. "
            f"Rules you MUST follow:\n"
            f"- Address the business by name ('{name}') at the start\n"
            f"- Write as a person, not a company — use first person (I/my)\n"
            f"- Do NOT leave any placeholders like [Name], [Company], [Title] etc.\n"
            f"- Sign off as 'Konstantinos' at the end\n"
            f"- Under 120 words\n"
            f"- Return ONLY the email body, no subject line, no explanations"
        )
        subject = f"Quick idea for {name}"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    body = response.choices[0].message.content.strip()
    return subject, body


def build_html(body: str, business_name: str, sender_email: str) -> str:
    # Sanitise newlines
    body_html = body.replace("\n", "<br>")
    unsub_text = (
        f"To unsubscribe from future emails, reply with 'UNSUBSCRIBE' "
        f"or email {sender_email} with the subject 'Unsubscribe'."
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body      {{ margin:0; padding:0; background:#0f1f1f; font-family:'Segoe UI',Arial,sans-serif; }}
  .wrap     {{ max-width:600px; margin:32px auto; background:#1a2e2e; border-radius:10px; overflow:hidden; border:1px solid rgba(255,255,255,0.08); }}
  .hdr      {{ background:#0a1414; padding:24px 36px; border-bottom:1px solid rgba(255,255,255,0.07); }}
  .hdr h1   {{ color:#fff; margin:0; font-size:20px; letter-spacing:3px; font-weight:800; }}
  .hdr p    {{ color:#6a9090; margin:4px 0 0; font-size:12px; }}
  .body     {{ padding:36px; color:#cde0de; font-size:15px; line-height:1.75; }}
  .body p   {{ margin:0 0 16px; }}
  .footer   {{ padding:20px 36px; border-top:1px solid rgba(255,255,255,0.07);
               color:#4a7070; font-size:11px; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>AUTOREACH</h1><p>Digital Presence Services</p></div>
  <div class="body"><p>{body_html}</p></div>
  <div class="footer">{unsub_text}</div>
</div>
</body>
</html>"""


def send_email(to_email: str, subject: str, html_body: str,
               gmail_user: str, gmail_pass: str) -> bool:
    """Returns True on success, False on failure."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = gmail_user
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        raise RuntimeError(f"SMTP error: {e}") from e

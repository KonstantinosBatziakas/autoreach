"""
Email generation + sending with rate limiting and unsubscribe footer.
Uses the Resend HTTP API (https://resend.com) instead of SMTP.
"""
import time
import re
import urllib.parse
import requests
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


def build_html(body: str, business_name: str, to_email: str,
               base_url: str = "https://app.autoreach.dev") -> str:
    """
    Build the HTML email.
    to_email is the recipient's address, used for the unsubscribe link.
    base_url should point to the running AutoReach server if self-hosting.
    """
    # Sanitise newlines
    body_html = body.replace("\n", "<br>")
    unsub_href = f"{base_url.rstrip('/')}/unsubscribe?email={urllib.parse.quote(to_email)}"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
  *     {{ box-sizing:border-box; margin:0; padding:0; }}
  body  {{ background:#080f0f; font-family:'Inter',Arial,sans-serif; padding:24px 12px; }}

  .wrap {{
    max-width:560px; margin:0 auto;
    background:#0d1a1a;
    border-radius:12px;
    overflow:hidden;
    border:1px solid rgba(78,205,196,0.12);
    box-shadow:0 0 40px rgba(0,0,0,0.6);
  }}

  /* ── Top accent bar ── */
  .accent-bar {{
    height:2px;
    background:linear-gradient(to right, transparent, #4ecdc4, #e8806a, transparent);
  }}

  /* ── Header ── */
  .hdr {{
    background:#060e0e;
    padding:22px 32px;
    display:flex;
    align-items:center;
    gap:14px;
    border-bottom:1px solid rgba(78,205,196,0.08);
  }}
  .hdr-icon {{
    width:36px; height:36px;
    background:linear-gradient(135deg,#4ecdc4,#2196f3);
    border-radius:8px;
    display:flex; align-items:center; justify-content:center;
    font-size:16px; flex-shrink:0;
  }}
  .hdr-text h1 {{
    color:#fff; font-size:14px; font-weight:600;
    letter-spacing:2.5px; text-transform:uppercase; margin:0;
  }}
  .hdr-text p {{
    color:#4a7a7a; font-size:11px; margin:2px 0 0;
    letter-spacing:0.5px;
  }}

  /* ── Body ── */
  .body {{
    padding:32px;
    color:#c8dede;
    font-size:14.5px;
    line-height:1.8;
  }}

  /* ── Divider ── */
  .divider {{
    height:1px;
    background:linear-gradient(to right, transparent, rgba(78,205,196,0.15), transparent);
    margin:0 32px;
  }}

  /* ── Footer ── */
  .footer {{
    padding:18px 32px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    flex-wrap:wrap;
    gap:10px;
  }}
  .footer-left {{
    color:#3a6060;
    font-size:11px;
    letter-spacing:0.3px;
    line-height:1.5;
  }}
  .unsub-btn {{
    display:inline-block;
    padding:5px 14px;
    border:1px solid rgba(78,205,196,0.2);
    border-radius:20px;
    color:#4a7070;
    font-size:10px;
    font-weight:500;
    letter-spacing:1px;
    text-transform:uppercase;
    text-decoration:none;
    transition:all 0.15s;
    white-space:nowrap;
  }}
  .unsub-btn:hover {{
    border-color:rgba(78,205,196,0.5);
    color:#4ecdc4;
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="accent-bar"></div>

  <div class="hdr">
    <div class="hdr-icon">✦</div>
    <div class="hdr-text">
      <h1>AutoReach</h1>
      <p>Digital Presence · Web Design · Marketing</p>
    </div>
  </div>

  <div class="body">{body_html}</div>

  <div class="divider"></div>

  <div class="footer">
    <div class="footer-left">
      You received this because your business was publicly listed.<br>
      We respect your inbox.
    </div>
    <a href="{unsub_href}" class="unsub-btn">Unsubscribe</a>
  </div>
</div>
</body>
</html>"""


def send_email(to_email: str, subject: str, html_body: str,
               resend_api_key: str, from_email: str) -> bool:
    """
    Send via the Resend HTTP API.
    Returns True on success, raises RuntimeError on failure.
    """
    if not resend_api_key:
        raise RuntimeError("resend_api_key is not configured. Add it via Settings or autoreach config.")
    if not from_email:
        from_email = "onboarding@resend.dev"

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Resend error {resp.status_code}: {detail}")
    return True

import re
import time
import requests
from bs4 import BeautifulSoup
from db import get_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

EMAIL_REGEX = r"[\w\.-]+@[\w\.-]+\.\w+"

def find_email_on_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        emails = re.findall(EMAIL_REGEX, response.text)
        emails = [e for e in emails if not any(e.endswith(x) for x in [".png", ".jpg", ".css", ".js", ".svg"])]
        if emails:
            return emails[0]
    except:
        pass
    return ""

def find_email_for_business(website):
    if not website:
        return ""
    website = website.rstrip("/")
    email = find_email_on_page(website)
    if email:
        return email
    for path in ["/contact", "/contact-us", "/about", "/about-us"]:
        time.sleep(1)
        email = find_email_on_page(website + path)
        if email:
            return email
    return ""

def scrape_emails():
    db = get_db()
    rows = [dict(r) for r in db.execute('SELECT id, name, website, email FROM businesses ORDER BY id').fetchall()]
    db.close()

    for i, business in enumerate(rows):
        if business.get("email"):
            continue
        print(f"[{i+1}] Checking {business['name']}...")
        email = find_email_for_business(business.get("website", ""))
        if email:
            print(f"     Found: {email}")
            db2 = get_db()
            db2.execute('UPDATE businesses SET email = ? WHERE name = ?', (email, business['name']))
            db2.commit()
            db2.close()
        else:
            print(f"     No email found")
        time.sleep(1)

    print("\nDone! Business emails updated in database.")

if __name__ == "__main__":
    scrape_emails()

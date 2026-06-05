import csv
import re
import time
import requests
from bs4 import BeautifulSoup

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

def scrape_emails(csv_file="businesses.csv"):
    rows = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for i, business in enumerate(rows):
        if business.get("email"):
            print(f"[{i+1}] {business['name']} - already has email, skipping")
            continue
        print(f"[{i+1}] Checking {business['name']}...")
        email = find_email_for_business(business.get("website", ""))
        if email:
            print(f"     Found: {email}")
            rows[i]["email"] = email
        else:
            print(f"     No email found")
        time.sleep(2)
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["name", "address", "phone", "website", "email"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print("\nDone! businesses.csv updated.")

if __name__ == "__main__":
    scrape_emails()
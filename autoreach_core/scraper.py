"""
Website email scraper.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS     = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
EMAIL_REGEX = r"[\w\.\-+]+@[\w\.-]+\.[a-zA-Z]{2,}"
BAD_EXTS    = (".png", ".jpg", ".jpeg", ".gif", ".css", ".js", ".svg", ".webp")


def _emails_on_page(url: str) -> list[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        found = re.findall(EMAIL_REGEX, r.text)
        return [e for e in found if not any(e.lower().endswith(x) for x in BAD_EXTS)]
    except Exception:
        return []


def find_email_for_website(website: str) -> str:
    if not website:
        return ""
    base = website.rstrip("/")
    emails = _emails_on_page(base)
    if emails:
        return emails[0]
    for path in ["/contact", "/contact-us", "/about", "/about-us", "/impressum"]:
        time.sleep(1)
        emails = _emails_on_page(base + path)
        if emails:
            return emails[0]
    return ""


def scrape_leads(leads: list[dict], progress_cb=None) -> list[dict]:
    """
    Takes a list of lead dicts (must have 'website').
    Returns the same list with 'email' filled in where found.
    progress_cb(i, total, name) called each iteration if provided.
    """
    total = len(leads)
    for i, lead in enumerate(leads):
        if progress_cb:
            progress_cb(i, total, lead.get("name", ""))
        if lead.get("email"):
            continue
        email = find_email_for_website(lead.get("website", ""))
        lead["email"] = email
        time.sleep(2)
    return leads

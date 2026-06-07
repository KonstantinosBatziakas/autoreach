import re
import time
import requests
from db import get_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Stricter pattern: TLD must be 2-6 alpha chars; skip obvious asset paths
EMAIL_REGEX = re.compile(r'[\w\.\-+]+@[\w\.\-]+\.[a-zA-Z]{2,6}')

# Extensions that never appear in real email addresses
_BAD_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.woff', '.ico', '.webp'}


def _extract_emails(text: str) -> list[str]:
    found = EMAIL_REGEX.findall(text)
    clean = []
    seen = set()
    for e in found:
        e_low = e.lower()
        if any(e_low.endswith(ext) for ext in _BAD_EXTENSIONS):
            continue
        if e_low in seen:
            continue
        seen.add(e_low)
        clean.append(e)
    return clean


def find_email_on_page(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        emails = _extract_emails(resp.text)
        if emails:
            return emails[0]
    except requests.RequestException:
        pass
    except Exception as exc:
        print(f'[scraper] Unexpected error fetching {url}: {exc}')
    return ''


def find_email_for_business(website: str) -> str:
    if not website:
        return ''
    website = website.rstrip('/')
    # Try homepage first
    email = find_email_on_page(website)
    if email:
        return email
    # Then common contact/about pages
    for path in ['/contact', '/contact-us', '/about', '/about-us']:
        time.sleep(0.8)
        email = find_email_on_page(website + path)
        if email:
            return email
    return ''


def scrape_emails():
    db = get_db()
    rows = [dict(r) for r in db.execute(
        'SELECT id, name, website, email FROM businesses ORDER BY id'
    ).fetchall()]
    db.close()

    found_count = 0
    for i, business in enumerate(rows):
        if business.get('email'):
            continue  # already have one
        name = business.get('name', '?')
        print(f'[{i + 1}/{len(rows)}] Scraping {name}…')
        email = find_email_for_business(business.get('website') or '')
        if email:
            print(f'  ✓ {email}')
            db2 = get_db()
            try:
                db2.execute(
                    'UPDATE businesses SET email = ? WHERE name = ?',
                    (email, name)
                )
                db2.commit()
                found_count += 1
            except Exception as exc:
                print(f'  [scraper] DB write failed for {name}: {exc}')
            finally:
                db2.close()
        else:
            print(f'  — no email found')
        time.sleep(1)

    print(f'\nDone! Found {found_count} new emails.')


if __name__ == '__main__':
    scrape_emails()

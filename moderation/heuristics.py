"""Conservative cold-email abuse heuristics; suspicious cases go to review."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse



URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly",
    "buff.ly", "cutt.ly", "shorturl.at", "rebrand.ly", "lnkd.in",
}
PAYMENT_OR_CREDENTIAL = re.compile(
    r"(?:password|passcode|login credentials|credit card|cvv|security code|"
    r"bank account|wire transfer|gift card|seed phrase|κωδικ(?:ο|ους|οι)|"
    r"στοιχει(?:α|α) συνδεση|κωδικο(?:ς|υς) προσβαση|αριθμο καρτα(?:ς)?|"
    r"στοιχεια καρτα(?:ς)?|τραπεζικ(?:ο|α) λογαριασμ(?:ο|ου))",
    re.I,
)
_REQUEST_WORD = re.compile(
    r"(?:send|share|provide|enter|reply with|confirm|verify|στείλε|δωσε|"
    r"παραχωρησε|συμπληρωσε|επιβεβαιωσε|στείλτε|δώστε|καταχωρηστε)", re.I,
)
FAKE_URGENCY = re.compile(
    r"(?:act now|immediately|within\s+\d+\s+hours?|expires? today|last chance|"
    r"urgent action|required today|your account (?:will|is about to)|"
    r"αμεσα|εντος\s+\d+\s+ωρ|ληγει σημερα|τελευταια ευκαιρια|"
    r"απαιτειται ενεργεια σημερα|ο λογαριασμος σας θα)", re.I,
)
KNOWN_BRANDS = (
    "google", "microsoft", "apple", "paypal", "amazon", "netflix", "meta",
    "facebook", "instagram", "bank of greece", "εθνικη τραπεζα", "πειραιως",
    "alpha bank", "eurobank",
)
IMPERSONATION = re.compile(
    r"(?:official|support|security|billing|account team|representative|"
    r"εκ μερους|επισημη υποστηριξη|τμημα ασφαλειας|λογαριασμο σας)", re.I,
)


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = ""
            self._text = []


def _host(value: str) -> str:
    try:
        parsed = urlparse(value if "://" in value else "https://" + value)
        return (parsed.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def check_email_heuristics(text: str) -> tuple[str, list[str]]:
    """Return (allow|review, categories); do not block ordinary cold outreach."""
    from moderation.service import normalization_forms, normalize_text
    categories: list[str] = []
    raw = text or ""
    urls = URL_RE.findall(raw)
    if len(urls) > 3:
        categories.append("excessive_links")
    if any(_host(url) in SHORTENER_DOMAINS for url in urls):
        categories.append("suspicious_link")

    parser = _AnchorParser()
    try:
        parser.feed(raw)
    except Exception:
        pass
    for target, label in parser.links:
        label_hosts = URL_RE.findall(label)
        if not label_hosts and re.search(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", label, re.I):
            label_hosts = [label]
        if label_hosts and any(_host(url) != _host(target) for url in label_hosts):
            categories.append("mismatched_link")
            break

    normalized_forms = normalization_forms(raw)
    normalized = "\n".join(normalized_forms)
    if PAYMENT_OR_CREDENTIAL.search(normalized) and _REQUEST_WORD.search(normalized):
        categories.append("credential_or_payment_request")
    if FAKE_URGENCY.search(normalized):
        categories.append("fake_urgency")
    lowered = normalize_text(raw)
    if any(brand in lowered for brand in KNOWN_BRANDS) and IMPERSONATION.search(raw):
        categories.append("possible_impersonation")

    letters = [c for c in raw if c.isalpha()]
    if len(letters) >= 40 and sum(c.isupper() for c in letters) / len(letters) > 0.55:
        categories.append("excessive_caps")
    if raw.count("!") >= 4:
        categories.append("excessive_exclamations")

    categories = list(dict.fromkeys(categories))
    return ("review" if categories else "allow", categories)

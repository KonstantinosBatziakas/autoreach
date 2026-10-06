"""Layered moderation, audit logging, user strikes, and encrypted queue storage."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from moderation.heuristics import check_email_heuristics
from moderation.providers import ModerationProviderError, classify


DATA_DIR = Path(__file__).with_name("data")
STRONG_BLOCK_CATEGORIES = {
    "profanity", "harassment_hate", "threats", "sexual_content",
    "scam_phishing_fraud", "impersonation", "deceptive_claims", "illegal_offers",
}


@dataclass(frozen=True)
class Decision:
    verdict: str
    categories: tuple[str, ...] = ()
    layer: str = "local"
    reason: str = ""
    audit_id: str | None = None
    enforcement_status: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch) and unicodedata.category(ch) != "Cf")
    text = text.translate(str.maketrans({
        "0": "o", "1": "i", "!": "i", "3": "e", "4": "a", "5": "s",
        "7": "t", "@": "a", "$": "s", "8": "b",
    }))
    # Collapse repeated characters but preserve double letters for normal words.
    text = re.sub(r"(.)\1{2,}", r"\1\1", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()


def normalization_forms(value: str) -> tuple[str, ...]:
    """Return normalized, spaced-letter, and Greeklish-transliterated forms."""
    text = normalize_text(value)
    # Greeklish transliteration uses common digraphs before single-character maps.
    table = (
        ("th", "θ"), ("ps", "ψ"), ("ks", "ξ"), ("ou", "ου"),
        ("ai", "αι"), ("ei", "ι"), ("oi", "ι"), ("mp", "μπ"),
        ("nt", "ντ"), ("gk", "γκ"), ("gg", "γγ"), ("ch", "χ"),
    )
    tokens = re.split(r"([^a-z]+)", text)
    greeklish_map = str.maketrans({
        "a": "α", "b": "β", "c": "κ", "d": "δ", "e": "ε", "f": "φ",
        "g": "γ", "h": "η", "i": "ι", "j": "τζ", "k": "κ", "l": "λ",
        "m": "μ", "n": "ν", "o": "ο", "p": "π", "q": "κ", "r": "ρ",
        "s": "σ", "t": "τ", "u": "υ", "v": "β", "w": "ω", "x": "ξ",
        "y": "υ", "z": "ζ",
    })
    for index, token in enumerate(tokens):
        if token and token.isascii() and token.isalpha():
            greek = token
            for source, target in table:
                greek = greek.replace(source, target)
            greek = greek.translate(greeklish_map)
            tokens[index] = greek
    greeklish = "".join(tokens)
    # Also test common spaced-out spelling (e.g. f u c k) without changing text.
    compact = re.sub(r"(?<!\w)(?:([a-z])\s+){2,}([a-z])(?!\w)",
                     lambda m: re.sub(r"\s+", "", m.group(0)), text)
    compact_greeklish = re.sub(r"(?<!\w)(?:([a-z])\s+){2,}([a-z])(?!\w)",
                              lambda m: re.sub(r"\s+", "", m.group(0)), greeklish)
    punctuation_spaced = re.sub(r"(?<!\w)(?:([a-z])[\s._-]+){2,}([a-z])(?!\w)",
                                lambda m: re.sub(r"[\s._-]+", "", m.group(0)), text)
    mixed_script = text.translate(str.maketrans({
        "α": "a", "а": "a", "ε": "e", "е": "e", "ο": "o", "о": "o",
        "ρ": "p", "р": "p", "с": "c", "χ": "x", "х": "x", "υ": "y",
        "у": "y", "ι": "i", "і": "i", "κ": "k", "т": "t",
    }))
    repeated_collapsed = re.sub(r"(.)\1+", r"\1", text, flags=re.S)
    return tuple(dict.fromkeys((text, repeated_collapsed, compact, greeklish, compact_greeklish, punctuation_spaced, mixed_script)))


def _list_words() -> list[str]:
    words: list[str] = []
    for filename in ("profanity_en.txt", "profanity_el.txt"):
        for line in (DATA_DIR / filename).read_text(encoding="utf-8").splitlines():
            word = line.strip()
            if word and not word.startswith("#"):
                words.append(word)
    return words


def _phrase_match(text: str, phrase: str) -> bool:
    for normalized_text in normalization_forms(text):
        normalized_phrase = normalize_text(phrase)
        if not normalized_phrase:
            return False
        # Match tokens as words; obscene roots in the data can intentionally end
        # in * so common inflections and adjacent suffixes are caught.
        parts = normalized_phrase.split()
        pattern = r"(?<![\w])" + r"\s+".join(re.escape(p.rstrip("*")) + (r"[\w]*" if p.endswith("*") else "") for p in parts) + r"(?![\w])"
        if re.search(pattern, normalized_text, re.I):
            return True
    return False


def _local_match(text: str, user_id: int, conn: Any) -> tuple[str, str] | None:
    for phrase in _list_words():
        if _phrase_match(text, phrase):
            return phrase, "profanity"
    try:
        rows = conn.execute(
            "SELECT phrase, type FROM blocklist WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        phrase, kind = row["phrase"], row["type"]
        normalized = normalize_text(text)
        if kind == "word" and _phrase_match(text, phrase):
            return phrase, "blocklist"
        if kind == "domain" and any(_domain_match(host, phrase) for host in re.findall(r"https?://([^/\s]+)", text, re.I)):
            return phrase, "blocklist_domain"
        if kind == "regex":
            try:
                if re.search(phrase, normalized, re.I):
                    return phrase, "blocklist_regex"
            except re.error:
                continue
    return None


def _domain_match(host: str, domain: str) -> bool:
    host, domain = host.lower().split(":", 1)[0].removeprefix("www."), domain.lower().removeprefix("www.")
    return host == domain or host.endswith("." + domain)


def _log(conn: Any, user_id: int, checkpoint: str, content_type: str, text: str,
         decision: Decision, action: str) -> str:
    excerpt = text[:240] if os.getenv("MODERATION_STORE_EXCERPT", "false").lower() == "true" else None
    audit_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO moderation_log
           (id, user_id, checkpoint, content_type, content_hash, content_excerpt,
            verdict, categories, layer, action_taken, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (audit_id, user_id, checkpoint, content_type, hashlib.sha256(text.encode("utf-8")).hexdigest(),
         excerpt, decision.verdict, json.dumps(list(decision.categories)), decision.layer,
         action, utc_now()),
    )
    conn.commit()
    return audit_id


def _add_strike(conn: Any, user_id: int) -> str:
    now = datetime.now(timezone.utc)
    decay_days = max(1, int(os.getenv("MODERATION_STRIKE_DECAY_DAYS", "90")))
    row = conn.execute("SELECT strike_count, last_strike_at FROM user_strikes WHERE user_id = ?", (user_id,)).fetchone()
    count = int(row["strike_count"]) if row else 0
    if row and row["last_strike_at"]:
        try:
            last = datetime.fromisoformat(row["last_strike_at"].replace("Z", "+00:00"))
            if now - last > timedelta(days=decay_days):
                count = 0
        except (ValueError, TypeError):
            pass
    count += 1
    status = "warned" if count == 1 else "rate_limited" if count == 2 else "suspended"
    notes = json.dumps({"last_reason": "moderation block", "strike_count": count})
    conn.execute(
        """INSERT INTO user_strikes (user_id, strike_count, last_strike_at, status, notes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET strike_count=excluded.strike_count,
             last_strike_at=excluded.last_strike_at, status=excluded.status, notes=excluded.notes""",
        (user_id, count, now.isoformat(timespec="seconds"), status, notes),
    )
    conn.commit()
    return status


def moderation_status(conn: Any, user_id: int) -> tuple[str, int]:
    row = conn.execute("SELECT status, strike_count, last_strike_at FROM user_strikes WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return "active", 0
    count = int(row["strike_count"])
    if row["last_strike_at"]:
        decay_days = max(1, int(os.getenv("MODERATION_STRIKE_DECAY_DAYS", "90")))
        try:
            last = datetime.fromisoformat(row["last_strike_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - last > timedelta(days=decay_days):
                conn.execute(
                    "UPDATE user_strikes SET strike_count=0, status='active', last_strike_at=NULL WHERE user_id=?",
                    (user_id,),
                )
                conn.commit()
                return "active", 0
        except (ValueError, TypeError):
            pass
    return row["status"], count


def _rate_limited(conn: Any, user_id: int) -> bool:
    status, _ = moderation_status(conn, user_id)
    if status == "suspended":
        return True
    if status != "rate_limited":
        return False
    hours = max(1, int(os.getenv("MODERATION_RATE_LIMIT_WINDOW_HOURS", "24")))
    maximum = max(1, int(os.getenv("MODERATION_RATE_LIMIT_MAX_SENDS", "1")))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM moderation_log WHERE user_id = ? AND checkpoint = 'send' AND action_taken = 'sent' AND created_at >= ?",
        (user_id, cutoff),
    ).fetchone()
    return int(row["n"] or 0) >= maximum


def check_content(text: str, user_id: int, checkpoint: str, content_type: str,
                  conn: Any, api_key: str | None = None) -> Decision:
    """Run local list, configured classifier, then cold-email heuristics."""
    raw = (text or "").strip()
    if checkpoint == "send" and _rate_limited(conn, user_id):
        decision = Decision("block", ("sending_suspended" if moderation_status(conn, user_id)[0] == "suspended" else "sending_rate_limited",), "local", "Your sending access is restricted after prior policy violations.")
        audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "refused")
        return Decision(**{**decision.__dict__, "audit_id": audit_id})
    match = _local_match(raw, user_id, conn)
    if match:
        decision = Decision("block", (match[1],), "local", "Remove abusive or blocked language before saving or sending.")
        audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "refused")
        status = _add_strike(conn, user_id)
        return Decision(**{**decision.__dict__, "audit_id": audit_id, "enforcement_status": status})

    classification = classify(raw, api_key=api_key)
    verdict = classification["verdict"]
    categories = tuple(dict.fromkeys(str(x) for x in classification.get("categories", [])))
    layer = "llm"
    reason = str(classification.get("reason", ""))[:240]
    if verdict == "block":
        decision = Decision("block", categories or ("other",), layer, reason or "This content violates the acceptable-use rules.")
        audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "refused")
        status = _add_strike(conn, user_id)
        return Decision(**{**decision.__dict__, "audit_id": audit_id, "enforcement_status": status})

    if content_type.startswith("email"):
        heuristic_verdict, heuristic_categories = check_email_heuristics(raw)
        if heuristic_verdict == "review":
            combined = tuple(dict.fromkeys(categories + tuple(heuristic_categories)))
            decision = Decision("review", combined, "heuristic", "This email needs a quick review before it can be sent.")
            audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "held_for_review")
            return Decision(**{**decision.__dict__, "audit_id": audit_id})

    if verdict == "review":
        decision = Decision("review", categories or ("other",), layer, reason or "This content needs review before it can be used.")
        audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "held_for_review")
        return Decision(**{**decision.__dict__, "audit_id": audit_id})

    decision = Decision("allow", categories, "llm", "Content passed the moderation checks.")
    audit_id = _log(conn, user_id, checkpoint, content_type, raw, decision, "allowed")
    return Decision(**{**decision.__dict__, "audit_id": audit_id})


def mark_sent(conn: Any, audit_id: str | None) -> None:
    if audit_id:
        conn.execute("UPDATE moderation_log SET action_taken = 'sent' WHERE id = ?", (audit_id,))
        conn.commit()


def moderate_and_queue(text: str, user_id: int, checkpoint: str, content_type: str,
                       conn: Any, payload: dict[str, Any] | None = None,
                       api_key: str | None = None) -> tuple[Decision, str | None]:
    """Evaluate content; preserve review/outage work in the encrypted queue."""
    try:
        decision = check_content(text, user_id, checkpoint, content_type, conn, api_key)
    except ModerationProviderError:
        decision = Decision(
            "review", ("moderation_unavailable",), "llm",
            "The moderation service is temporarily unavailable. This item is queued and will be checked before use.",
        )
        _log(conn, user_id, checkpoint, content_type, text, decision, "queued_for_retry")
        queue_id = enqueue(conn, user_id, checkpoint, content_type, payload or {"content": text}, "retry", decision.categories)
        return decision, queue_id
    if decision.verdict == "review":
        queue_id = enqueue(conn, user_id, checkpoint, content_type, payload or {"content": text}, "needs_review", decision.categories)
        return decision, queue_id
    return decision, None


def _fernet() -> Fernet:
    configured = os.getenv("MODERATION_ENCRYPTION_KEY", "").strip()
    if configured:
        return Fernet(configured.encode("ascii"))
    secret = os.getenv("SECRET_KEY", "autoreach-insecure-dev-key-change-me").encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


def enqueue(conn: Any, user_id: int, checkpoint: str, content_type: str,
            payload: dict[str, Any], status: str, categories: list[str] | tuple[str, ...]) -> str:
    encrypted = _fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    now = utc_now()
    queue_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO moderation_queue
           (id, user_id, checkpoint, content_type, payload_enc, status, categories,
            attempts, next_attempt_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
        (queue_id, user_id, checkpoint, content_type, encrypted, status,
         json.dumps(list(categories)), now, now, now),
    )
    conn.commit()
    return queue_id


def decrypt_payload(value: str) -> dict[str, Any]:
    return json.loads(_fernet().decrypt(value.encode("ascii")).decode("utf-8"))


def retry_delay(attempts: int) -> str:
    minutes = min(60, 2 ** min(attempts, 6))
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")

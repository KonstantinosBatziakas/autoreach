"""Send gate shared by Flask, CLI, and follow-up senders."""

from __future__ import annotations

from typing import Any, Callable

import requests

from moderation.service import Decision, mark_sent, moderate_and_queue


class DeliveryBlocked(RuntimeError):
    def __init__(self, decision: Decision):
        self.decision = decision
        super().__init__(user_message(decision))


class DeliveryQueued(RuntimeError):
    def __init__(self, queue_id: str, decision: Decision):
        self.queue_id = queue_id
        self.decision = decision
        super().__init__(decision.reason or "This email is held for review.")


def user_message(decision: Decision) -> str:
    labels = {
        "profanity": "vulgar or abusive language",
        "harassment_hate": "harassment or hateful content",
        "threats": "threatening content",
        "sexual_content": "sexual content",
        "scam_phishing_fraud": "scam, phishing, or fraud indicators",
        "impersonation": "possible impersonation",
        "deceptive_claims": "deceptive claims",
        "illegal_offers": "an illegal offer",
        "blocklist": "a phrase on your blocklist",
        "blocklist_domain": "a domain on your blocklist",
        "blocklist_regex": "a pattern on your blocklist",
        "sending_rate_limited": "a temporary sending restriction",
        "sending_suspended": "a sending suspension pending review",
    }
    categories = [labels.get(category, category.replace("_", " ")) for category in decision.categories]
    reason = ", ".join(categories) if categories else "content that violates the acceptable-use policy"
    status_message = {
        "warned": "This is a warning.",
        "rate_limited": "Your sending is temporarily rate-limited after repeated violations.",
        "suspended": "Your sending is suspended pending administrator review.",
    }.get(decision.enforcement_status, "")
    return f"This content was blocked for {reason}. {status_message} Edit it and resubmit. See /acceptable-use for the policy."


def send_resend(payload: dict[str, Any], queue_id: str | None = None) -> None:
    key = (payload.get("resend_api_key") or "").strip()
    if not key:
        raise RuntimeError("Resend API key not provided.")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if queue_id:
        headers["Idempotency-Key"] = f"autoreach-moderation-{queue_id}"
    response = requests.post(
        "https://api.resend.com/emails", headers=headers,
        json={"from": payload.get("from_email") or "onboarding@resend.dev",
              "to": [payload["email"]], "subject": payload["subject"],
              "html": payload.get("html") or payload.get("body", "")},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Resend returned HTTP {response.status_code}.")


def send_moderated(payload: dict[str, Any], user_id: int, conn: Any,
                   sender: Callable[[dict[str, Any], str | None], None] = send_resend,
                   api_key: str | None = None) -> Decision:
    content = f"Subject: {payload.get('subject', '')}\n\n{payload.get('body', '')}"
    decision, queue_id = moderate_and_queue(
        content, user_id, "send", "email", conn,
        payload={**payload, "user_id": user_id}, api_key=api_key,
    )
    if decision.verdict == "block":
        raise DeliveryBlocked(decision)
    if decision.verdict == "review" or queue_id:
        raise DeliveryQueued(queue_id or "", decision)
    sender(payload, None)
    mark_sent(conn, decision.audit_id)
    return decision

"""Retry encrypted moderation-provider outage jobs; never bypass re-checks."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable

from moderation.delivery import send_resend
from moderation.providers import ModerationProviderError
from moderation.service import check_content, decrypt_payload, mark_sent, retry_delay


def retry_queued(conn: Any, user_id: int | None = None,
                 sender: Callable[[dict[str, Any], str | None], None] = send_resend,
                 on_delivered: Callable[[dict[str, Any], int], None] | None = None) -> dict[str, int]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    query = "SELECT * FROM moderation_queue WHERE status = 'retry' AND next_attempt_at <= ?"
    params: list[Any] = [now]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    query += " ORDER BY created_at LIMIT 50"
    rows = conn.execute(query, tuple(params)).fetchall()
    stats = {"delivered": 0, "review": 0, "blocked": 0, "retry": 0}
    for row in rows:
        queue_id = row["id"]
        owner_id = int(row["user_id"])
        try:
            payload = decrypt_payload(row["payload_enc"])
            if payload.get("user_id") not in (None, owner_id):
                raise ValueError("queue owner mismatch")
            text = f"Subject: {payload.get('subject', '')}\n\n{payload.get('body') or payload.get('content', '')}"
            decision = check_content(text, owner_id, row["checkpoint"], row["content_type"], conn,
                                     api_key=payload.get("moderation_api_key"))
        except ModerationProviderError:
            attempts = int(row["attempts"]) + 1
            conn.execute(
                "UPDATE moderation_queue SET attempts=?, next_attempt_at=?, updated_at=? WHERE id=?",
                (attempts, retry_delay(attempts), now, queue_id),
            )
            conn.commit()
            stats["retry"] += 1
            continue
        except Exception:
            conn.execute("UPDATE moderation_queue SET status='blocked', updated_at=? WHERE id=?", (now, queue_id))
            conn.commit()
            stats["blocked"] += 1
            continue

        if decision.verdict == "block":
            conn.execute("UPDATE moderation_queue SET status='blocked', categories=?, updated_at=? WHERE id=?",
                         (json.dumps(list(decision.categories)), now, queue_id))
            conn.commit()
            stats["blocked"] += 1
            continue
        if decision.verdict == "review" or row["checkpoint"] != "send":
            conn.execute("UPDATE moderation_queue SET status='needs_review', categories=?, updated_at=? WHERE id=?",
                         (json.dumps(list(decision.categories)), now, queue_id))
            conn.commit()
            stats["review"] += 1
            continue

        try:
            sender(payload, queue_id)
            mark_sent(conn, decision.audit_id)
            if on_delivered:
                on_delivered(payload, owner_id)
        except Exception:
            attempts = int(row["attempts"]) + 1
            conn.execute(
                "UPDATE moderation_queue SET attempts=?, next_attempt_at=?, updated_at=? WHERE id=?",
                (attempts, retry_delay(attempts), now, queue_id),
            )
            conn.commit()
            stats["retry"] += 1
            continue

        conn.execute("UPDATE moderation_queue SET status='delivered', categories='[]', updated_at=? WHERE id=?",
                     (now, queue_id))
        conn.commit()
        stats["delivered"] += 1
    return stats

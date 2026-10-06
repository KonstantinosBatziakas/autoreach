import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from moderation import service
from moderation.delivery import DeliveryBlocked, DeliveryQueued, send_moderated
from moderation.heuristics import check_email_heuristics
from moderation.providers import ModerationProviderError


class ModerationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE moderation_log (
              id TEXT PRIMARY KEY, user_id INTEGER, checkpoint TEXT, content_type TEXT,
              content_hash TEXT, content_excerpt TEXT, verdict TEXT, categories TEXT,
              layer TEXT, action_taken TEXT, created_at TEXT);
            CREATE TABLE user_strikes (
              user_id INTEGER PRIMARY KEY, strike_count INTEGER, last_strike_at TEXT,
              status TEXT, notes TEXT);
            CREATE TABLE blocklist (
              id TEXT PRIMARY KEY, user_id INTEGER, phrase TEXT, language TEXT,
              type TEXT, added_by INTEGER, created_at TEXT);
            CREATE TABLE moderation_queue (
              id TEXT PRIMARY KEY, user_id INTEGER, checkpoint TEXT, content_type TEXT,
              payload_enc TEXT, status TEXT, categories TEXT, attempts INTEGER,
              next_attempt_at TEXT, created_at TEXT, updated_at TEXT);
        """)
        self.allow = patch.object(service, "classify", return_value={"verdict": "allow", "categories": [], "reason": ""})
        self.allow.start()
        self.addCleanup(self.allow.stop)

    def tearDown(self):
        self.conn.close()

    def test_normalization_handles_greek_diacritics_leetspeak_repeats_and_spacing(self):
        self.assertTrue(service._phrase_match("μαλάκα", "μαλακ*"))
        self.assertTrue(service._phrase_match("gamw", "γαμ*"))
        self.assertTrue(service._phrase_match("fuuuuck", "fuck*"))
        self.assertTrue(service._phrase_match("f u c k", "fuck*"))
        self.assertTrue(service._phrase_match("sh1t", "shit*"))

    def test_editable_user_blocklist_is_user_scoped(self):
        self.conn.execute(
            "INSERT INTO blocklist VALUES ('b1', 4, 'bad offer', 'en', 'word', 4, 'now')"
        )
        self.assertEqual(service._local_match("This is a bad offer", 4, self.conn)[1], "blocklist")
        self.assertIsNone(service._local_match("This is a bad offer", 5, self.conn))

    def test_heuristics_review_suspicious_links_and_credentials(self):
        self.assertIn("suspicious_link", check_email_heuristics("Visit https://bit.ly/offer")[1])
        result = check_email_heuristics("<a href='https://evil.example'>paypal.com</a>")
        self.assertIn("mismatched_link", result[1])
        result = check_email_heuristics("Please send your password immediately.")
        self.assertIn("credential_or_payment_request", result[1])

    def test_llm_block_is_logged_with_classification_category(self):
        with patch.object(service, "classify", return_value={
            "verdict": "block", "categories": ["scam_phishing_fraud"], "reason": "phishing"
        }):
            decision = service.check_content("A fake billing message", 6, "save", "email_template", self.conn)
        self.assertEqual(decision.verdict, "block")
        self.assertEqual(decision.layer, "llm")
        self.assertEqual(decision.categories, ("scam_phishing_fraud",))

    def test_strikes_decay_to_active_after_configured_period(self):
        self.conn.execute(
            "INSERT INTO user_strikes VALUES (23, 3, '2020-01-01T00:00:00+00:00', 'suspended', 'old')"
        )
        with patch.dict("os.environ", {"MODERATION_STRIKE_DECAY_DAYS": "30"}):
            self.assertEqual(service.moderation_status(self.conn, 23), ("active", 0))

    def test_strike_ladder_and_decay_statuses(self):
        for expected in ("warned", "rate_limited", "suspended"):
            decision = service.check_content("fuck this", 17, "save", "email_template", self.conn)
            self.assertEqual(decision.verdict, "block")
            self.assertEqual(service.moderation_status(self.conn, 17)[0], expected)
        self.assertEqual(service.moderation_status(self.conn, 17)[1], 3)

    def test_provider_outage_is_encrypted_retry_queue_and_never_delivery(self):
        delivered = []
        with patch.object(service, "classify", side_effect=ModerationProviderError("down")):
            decision, queue_id = service.moderate_and_queue(
                "A clean message", 9, "send", "email", self.conn,
                payload={"email": "x@example.com", "subject": "Hello", "body": "A clean message"},
            )
        self.assertEqual(decision.verdict, "review")
        row = self.conn.execute("SELECT * FROM moderation_queue WHERE id=?", (queue_id,)).fetchone()
        self.assertEqual(row["status"], "retry")
        self.assertEqual(service.decrypt_payload(row["payload_enc"])["email"], "x@example.com")
        with patch.object(service, "classify", side_effect=ModerationProviderError("down")):
            with self.assertRaises(DeliveryQueued):
                send_moderated(
                    {"email": "x@example.com", "subject": "Hello", "body": "A clean message"},
                    9, self.conn, sender=lambda payload, key: delivered.append(payload),
                )
        self.assertEqual(delivered, [])

    def test_clean_greek_and_english_cold_emails_are_not_flagged(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures/clean_emails.json").read_text(encoding="utf-8"))
        for fixture in fixtures:
            text = f"Subject: {fixture['subject']}\n\n{fixture['body']}"
            self.assertIsNone(service._local_match(text, 2, self.conn))
            self.assertEqual(check_email_heuristics(text)[0], "allow")
            self.assertEqual(service.check_content(text, 2, "generate", "email", self.conn).verdict, "allow")

    def test_authoritative_send_checks_content_before_sender(self):
        delivered = []
        with self.assertRaises(DeliveryBlocked):
            send_moderated(
                {"email": "victim@example.com", "subject": "Hello", "body": "fuck you"},
                3, self.conn, sender=lambda payload, key: delivered.append(payload),
            )
        self.assertEqual(delivered, [])


if __name__ == "__main__":
    unittest.main()

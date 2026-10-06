import importlib
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


class SendApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="autoreach-moderation-")
        os.environ["DATA_DIR"] = cls.data_dir.name
        os.environ["APP_ENV"] = "development"
        os.environ["MODERATION_RETRY_WORKER_ENABLED"] = "false"
        os.environ.pop("WEB_PASSWORD", None)
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.testing = True
        db = cls.app_module.get_db()
        db.execute("INSERT INTO settings(key,value) VALUES('accepted_aup_version',?)", (cls.app_module.AUP_VERSION,))
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        cls.data_dir.cleanup()

    def test_direct_send_email_request_cannot_bypass_block(self):
        with patch("moderation.service.classify", return_value={"verdict": "allow", "categories": [], "reason": ""}), \
             patch.object(self.app_module, "send_moderated", wraps=self.app_module.send_moderated) as gate:
            response = self.app_module.app.test_client().post(
                "/api/send-email",
                json={"business_name": "Test", "email": "recipient@example.com",
                      "subject": "Hello", "body": "fuck you", "resend_api_key": "re_test"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("acceptable-use", response.get_json()["policy_url"])
        self.assertEqual(gate.call_count, 1)

    def test_password_login_requires_policy_acceptance(self):
        response = self.app_module.app.test_client().post(
            "/auth/login", json={"email": "person@example.com", "password": "correct horse"}
        )
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.get_json()["code"], "aup_required")

    def test_migration_preserves_existing_accounts_and_applies_moderation_schema(self):
        with tempfile.TemporaryDirectory(prefix="autoreach-legacy-db-") as legacy_dir:
            db_path = os.path.join(legacy_dir, "autoreach.db")
            legacy = sqlite3.connect(db_path)
            legacy.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, provider_id TEXT NOT NULL, email TEXT, name TEXT, avatar_url TEXT, password_hash TEXT, created_at TEXT)")
            legacy.execute("INSERT INTO users(id,provider,provider_id,email,name) VALUES (7,'email','p@example.com','p@example.com','P')")
            legacy.execute("CREATE TABLE oauth_state (state TEXT PRIMARY KEY, provider TEXT NOT NULL, created_at TEXT)")
            legacy.commit(); legacy.close()
            old_dir = os.environ["DATA_DIR"]
            os.environ["DATA_DIR"] = legacy_dir
            try:
                self.app_module.init_db()
                migrated = sqlite3.connect(db_path)
                columns = {row[1] for row in migrated.execute("PRAGMA table_info(users)")}
                row = migrated.execute("SELECT email, role, accepted_aup_version FROM users WHERE id=7").fetchone()
                tables = {row[0] for row in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                migrated.close()
            finally:
                os.environ["DATA_DIR"] = old_dir
            self.assertTrue({'role', 'accepted_aup_version', 'accepted_aup_at'} <= columns)
            self.assertEqual(row, ('p@example.com', 'user', None))
            self.assertTrue({'moderation_log', 'user_strikes', 'blocklist', 'moderation_queue'} <= tables)

    def test_flutter_and_cli_are_wired_to_shared_authoritative_route(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "autoreach_flutter/lib/screens/outreach_screen.dart"), encoding="utf-8") as f:
            flutter_source = f.read()
        with open(os.path.join(root, "emailer.py"), encoding="utf-8") as f:
            cli_source = f.read()
        with open(os.path.join(root, "cli/main.py"), encoding="utf-8") as f:
            modern_cli_source = f.read()
        self.assertIn("/api/send-email", flutter_source)
        self.assertIn("send_moderated(", cli_source)
        self.assertIn("from moderation.delivery import", cli_source)
        self.assertIn("send_moderated(", modern_cli_source)


if __name__ == "__main__":
    unittest.main()

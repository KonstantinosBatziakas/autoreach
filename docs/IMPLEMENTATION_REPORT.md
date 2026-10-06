# AutoReach Implementation Self-Review

Reviewed branch: `step3-content-moderation`
Reviewed HEAD: `5a11dacf951c8b653c7e691692d278ab0414ff88`
Step 3 implementation: `03e94b81232aa234a90e1416142c223aa4355943`, with policy page `bb4c3d051db7242690e12c807b635a21fbc322f6`
Prior Step 2 baseline: `9e5dae7` (ARIA BYOK/settings)

## 1. Audit issues (items 1–26)

Each item is assessed against the reviewed HEAD. “Not fixed” means the finding remains outside this Step 3 implementation; moderation-related additions do not imply that the broader audit item is resolved.

| # | Status | Finding and evidence |
|---|---|---|
| 1 | Not fixed | The authoritative send route now moderates content, but `/api/send-email` still does not enforce duplicate-send or unsubscribe suppression itself. The lead listing filters sent and unsubscribed leads, which is not an authoritative send guard. Reviewed at `5a11dac`; `app.py` (`api_send_email`, `api_leads`). |
| 2 | Partially fixed | New moderation records, strikes, queues and blocklist rows carry `user_id`; the existing leads, settings, sent logs and campaign data remain shared/global. Reviewed at `03e94b8`; `migrations/001_content_moderation.sql`, `autoreach_core/db.py`, `app.py`. |
| 3 | Partially fixed | Protected web routes now fail closed when production auth is unconfigured, and APIs require a valid JWT or configured session plus AUP acceptance. The wider auth/session model and coverage of every legacy route have not been comprehensively repaired. Reviewed at `03e94b8`; `app.py` (`web_login_required`), `auth.py`. |
| 4 | Not fixed | The setup wizard still writes secrets to a local `.env` file and has not been hardened as a production secret-management flow. Reviewed at `5a11dac`; `app.py` (`setup`). |
| 5 | Not fixed | The app still uses an insecure fallback `SECRET_KEY` and warns at startup. Configure a real secret. Reviewed at `5a11dac`; `app.py`, `auth.py`, `moderation/service.py`. |
| 6 | Partially fixed | Password minimum length/hash checks exist, and protected requests now require authentication. Rate limiting for login, complete CSRF protection and safe redirect validation remain open. Reviewed at `5a11dac`; `auth.py`, `app.py` (`web_login`, `web_login_required`). |
| 7 | Partially fixed | ARIA now supports user-selected OpenAI-compatible providers, stores prompts locally, and moderates custom prompts before save. There is no server proxy rate limiter or server-side conversation-history policy; a user can also call their own provider outside AutoReach. Reviewed at `5a11dac`; `templates/aria.html`, `autoreach_flutter/lib/screens/aria_screen.dart`, `autoreach_flutter/lib/services/aria_prompt_service.dart`, `9e5dae7`. |
| 8 | Partially fixed | New send/moderation failures return generic messages and log server details, but older API routes still return exception text/tracebacks. Reviewed at `5a11dac`; `app.py` (`api_all_leads`, `api_sent`, `api_leads`, scraper/report routes). |
| 9 | Not fixed | Messages are still delivered as HTML without a plain-text alternative or `List-Unsubscribe` headers. Reviewed at `5a11dac`; `moderation/delivery.py`, `emailer.py`, `autoreach_core/emailer.py`. |
| 10 | Partially fixed | Unsubscribe state and filtering exist, but links still identify recipients by email query parameter and there is no signed token or bounce webhook. `/api/send-email` also lacks an unsubscribe check. Reviewed at `5a11dac`; `app.py` (`unsubscribe`, `api_send_email`, `api_leads`), `emailer.py`. |
| 11 | Partially fixed | The web email renderer now escapes body and sender values. Other renderers, including the core/legacy email builders, still need a complete output-escaping review. Reviewed at `03e94b8`; `app.py` (`_build_email_html`), `autoreach_core/emailer.py`, `followup.py`. |
| 12 | Not fixed | Branding and footer text remain hard-coded in several email templates and renderers. Reviewed at `5a11dac`; `app.py` (`_build_email_html`), `autoreach_core/emailer.py`, `followup.py`. |
| 13 | Not fixed | A physical postal address/sender identity requirement has not been added to outbound email. Reviewed at `5a11dac`; `app.py` (`_build_email_html`), `templates/outreach.html`. |
| 14 | Partially fixed | Existing per-run pacing remains; moderation adds configurable strike-based rate limits and retry queues. Campaign sending windows, campaign caps and a durable distributed job system remain open. Reviewed at `03e94b8`; `moderation/service.py`, `moderation/queue.py`, `app.py`, `autoreach_core/emailer.py`. |
| 15 | Disputed | The product direction is BYOK: users supply their own provider and delivery credentials. The send API therefore receives a Resend key from the client; pending retries encrypt the key and message payload. This differs from the audit’s server-side key-storage recommendation by design, but means the hosted server handles the key in memory and encrypted queue storage. Reviewed at `03e94b8` and `9e5dae7`; `app.py` (`api_send_email`), `moderation/service.py`, `moderation/delivery.py`, `autoreach_flutter/lib/services/settings_service.dart`. |
| 16 | Not fixed | Some lead mutations still select by business name rather than stable primary-key ID. Reviewed at `5a11dac`; `app.py` (`api_update_stage`, `update_stage`), `templates/leads.html`. |
| 17 | Partially fixed | The form `/update_stage` validates against known stages, but `/api/update-stage` still accepts arbitrary non-empty stage values and updates by name. Reviewed at `5a11dac`; `app.py` (`update_stage`, `api_update_stage`). |
| 18 | Not fixed | `write_businesses` still deletes and reinserts the full lead table. Reviewed at `5a11dac`; `app.py` (`write_businesses`). |
| 19 | Partially fixed | CSV import skips duplicate names and requires a `.csv` suffix, but it lacks file-size limits, robust encoding fallback and strict header/row validation. Reviewed at `5a11dac`; `app.py` (`import_leads`). |
| 20 | Partially fixed | Dashboard count helpers handle empty/NULL counts; most application timestamps and daily windows still use local time rather than consistently stored UTC timestamps. Reviewed at `5a11dac`; `app.py` (`count_stats`, send/follow-up timestamps), `followup.py`, `autoreach_core/db.py`. |
| 21 | Not fixed | Background work still runs in in-process threads; moderation retry is also an in-process worker and is not a durable distributed job queue. Reviewed at `03e94b8`; `app.py` (`_daily_followup_thread`, `_moderation_retry_thread`), `followup.py`. |
| 22 | Not fixed | `app.py` remains a large monolithic Flask module. Reviewed at `5a11dac`; `app.py`. |
| 23 | Partially fixed | Added moderation privacy/configuration documentation, a changelog and dashboard notes. Several pre-existing README/deployment descriptions remain stale and need a full documentation pass. Reviewed at `03e94b8` and `5a11dac`; `README_DASHBOARD.md`, `docs/PRIVACY_MODERATION.md`, `docs/privacy.html`, `CHANGELOG.md`. |
| 24 | Fixed | Product copy now says “source-available” rather than “open source,” consistent with the custom source-available license. Reviewed/fixed in `5a11dac`; `README.md`, `docs/index.html`, `docs/privacy.html`, `docs/aria.html`, `templates/aria.html`, `templates/unsubscribe.html`, `autoreach_flutter/lib/screens/login_screen.dart`, `autoreach_flutter/lib/services/aria_prompt_service.dart`. |
| 25 | Partially fixed | `.env.example` documents moderation provider, model, keys, encryption and strike settings. Hosted deployment manifests were not comprehensively updated or exercised. Reviewed at `03e94b8`; `.env.example`, `render.yaml`, `fly.toml`, `railway.json`, `Dockerfile`. |
| 26 | Partially fixed | Added Python moderation/integration tests and Flutter tests, and declared `cryptography`. No CI workflow, full dependency/security audit or secret-history scan was added. Flutter analyze could not complete because the bundled Dart analysis server crashed. Reviewed at `03e94b8`; `tests/`, `autoreach_flutter/test/`, `requirements.txt`. |

## 2. Features A–J

| Feature | Status | Evidence / remaining work |
|---|---|---|
| A. Campaigns | Not implemented | No campaigns entity with per-campaign stats, pause/resume or campaign approval queue was added. The moderation queue is for individual checked content, not campaign management. Reviewed at `5a11dac`; `app.py`, `autoreach_core/db.py`. |
| B. Replies and bounces | Partially implemented | Manual reply tracking and follow-up cancellation exist. Bounce webhook/provider ingestion and automatic bounce suppression remain absent. Reviewed at `5a11dac`; `autoreach_core/db.py`, `autoreach_core/followup.py`, `app.py`. |
| C. Email verification | Not implemented | No email verification flow or verified-address state was added. Reviewed at `5a11dac`; `auth.py`, `app.py`. |
| D. Generation improvements | Partially implemented | Personalization and user prompts exist; custom prompts and generated emails receive moderation. A/B testing, outcome-driven optimization and a broad generation quality pass are not implemented. Reviewed at `03e94b8`, `5a11dac`; `autoreach_core/emailer.py`, `autoreach_flutter/lib/screens/outreach_screen.dart`, `templates/outreach.html`, `moderation/`. |
| E. Lead finder | Partially implemented | Google Maps lead search and CSV export exist. Search pagination, dedupe beyond current name checks, advanced filters, grid/scoring and export improvements remain. Reviewed at `5a11dac`; `lead_finder.py`, `app.py`, `templates/find_leads.html`. |
| F. Follow-up sequences | Partially implemented | Three scheduled follow-ups and manual reply checks exist, and follow-up generation/send now uses moderation. Send windows and richer response/condition logic remain. Reviewed at `03e94b8`; `followup.py`, `autoreach_core/followup.py`, `moderation/delivery.py`. |
| G. Analytics | Partially implemented | Summary counts and reports exist; interactive charts and deeper campaign metrics were not added. Reviewed at `5a11dac`; `app.py` (`count_stats`), `templates/index.html`, `templates/report.html`. |
| H. Account settings | Partially implemented | Flutter stores user API keys securely on-device, exposes sender identity, and supports provider/model/prompt settings. Server-wide encrypted per-user credential management, timezone preferences, full localization and test-send flows remain. Reviewed at `9e5dae7`, `03e94b8`; `autoreach_flutter/lib/services/settings_service.dart`, `autoreach_flutter/lib/screens/settings_screen.dart`, `app.py`. |
| I. Admin operations | Partially implemented | Added role-protected moderation log, blocklist and strike management. General health endpoint, Sentry, centralized structured logging, backup operations and full migration tooling remain. Reviewed at `03e94b8`; `templates/moderation_admin.html`, `app.py`, `migrations/`. |
| J. Flutter and CLI parity | Partially implemented | Both Flutter and CLI paths use the shared server/send moderation check; Flutter, web and modern CLI can review held email. The product features remain uneven across clients, and the legacy root CLI does not provide the modern review workflow for every content type. Reviewed at `03e94b8`; `autoreach_flutter/lib/screens/outreach_screen.dart`, `autoreach_flutter/lib/screens/moderation_queue_screen.dart`, `cli/main.py`, `emailer.py`. |

## 3. Moderation (Step 3)

| Prompt section | Status | Deviations |
|---|---|---|
| 3.1 Moderation checkpoints | Partially implemented | Save checks cover email templates and custom ARIA prompts; generation checks cover web, Flutter, core/CLI and follow-up generation; all direct sends and both follow-up senders recheck server-side. `campaign_instructions` is accepted as a moderation content type, but this repo has no campaign-instructions editor/storage flow to hook. Flutter/CLI generation tests are not full device/terminal end-to-end tests. |
| 3.2 Layered checks | Partially implemented | Implemented local normalization/data lists, configured LLM provider and cold-email heuristics in that order. The Groq default is configurable; the currently documented `openai/gpt-oss-safeguard-20b` is a Preview model. The OpenAI moderation-endpoint adapter uses OpenAI's built-in category taxonomy, whose coverage is not equivalent to the requested scam/impersonation/deceptive-claims taxonomy. Heuristics send uncertain content to review; provider behavior and false-positive rates require live evaluation. |
| 3.3 Database | Implemented with schema differences | Added versioned SQLite/Turso SQL migration and matching local core tables. `categories` is JSON-serialized text, not a database-native JSON type. Excerpt storage defaults off. Encrypted queue is an additional table beyond the listed tables. User data outside the moderation tables remains shared in legacy schemas. |
| 3.4 Enforcement | Implemented with client limitations | Blocks refuse, return plain categories/policy links and add strikes; review/retry items are encrypted and rechecked; strike ladder, decay, admin reset/override and admin log/blocklist screens exist. The admin role must be assigned through the database or `MODERATION_ADMIN_USER_IDS`; no admin provisioning UI was added. The in-process retry worker is not durable across process loss, though queued rows persist and retry on the next worker run. The optional admin review screen for deciding held messages was not added. |
| 3.5 Terms and transparency | Implemented | Added bilingual acceptable-use page and required current-version acceptance for registration, password login, OAuth and protected routes. Stored acceptance version/timestamp per account, with legacy web session stored in settings. Updated the privacy page and added deployment/privacy notes. Operators still need to deploy matching public privacy disclosures and retention settings. |
| 3.6 Tests | Partially implemented | Python tests cover normalization, local/LLM/heuristic layers, strikes, decay, queue encryption/fail-safe, clean English/Greek fixtures and direct blocked `/api/send-email`. Migration preservation and policy-login behavior are tested. Flutter tests pass; the API test verifies Flutter/CLI route wiring, but it does not launch a real Flutter client or exercise a real CLI send against a test Resend server. No live Groq/OpenAI/Resend calls were made. |

## 4. Remaining work (prioritized)

1. Add authoritative duplicate-send and unsubscribe/suppression checks to `/api/send-email`; add signed unsubscribe tokens and bounce ingestion.
2. Replace the insecure `SECRET_KEY` fallback, harden setup secrets, and finish login rate limits, CSRF controls and redirect validation.
3. Add an actual campaign model and a campaign-instructions save path; then enforce moderation at that save point.
4. Run provider integration and false-positive trials with authorized Groq/OpenAI and Resend test accounts; tune Greek/Greeklish fixtures based on results.
5. Add CI, dependency/security checks, secret-history scanning and a reliable Flutter analyzer environment.
6. Move retry/follow-up work to a durable worker/queue and add queue retention cleanup. Existing queue content and delivery keys remain encrypted in rows after delivery until database cleanup.
7. Complete the broader audit findings listed above: multi-tenant leads/settings/logs, email text alternatives/headers, address identity, stable lead IDs, safer CSV import, UTC timestamps, modularize `app.py`, deployment docs and platform parity.
8. Add admin provisioning and optional admin review decisions for held items; give legacy CLI users the same queue UX for prompts/templates.

## 5. Risks and assumptions

- **Provider cost and availability:** Groq's official model page lists `openai/gpt-oss-safeguard-20b` as Preview. Model availability, limits and provider pricing can change. Configure `MODERATION_MODEL` and monitor provider failures. See [Groq's model page](https://console.groq.com/docs/model/openai/gpt-oss-safeguard-20b) and [supported models](https://console.groq.com/docs/models).
- **Required config:** Set a strong `SECRET_KEY`; set a stable `MODERATION_ENCRYPTION_KEY` (recommended); set `MODERATION_PROVIDER=groq` or `openai`; provide `MODERATION_API_KEY` or the provider-specific key; configure `MODERATION_MODEL` for Groq; retain `MODERATION_STORE_EXCERPT=false` unless the privacy notice and retention terms are updated. Strike/rate defaults are configurable with `MODERATION_STRIKE_DECAY_DAYS`, `MODERATION_RATE_LIMIT_WINDOW_HOURS` and `MODERATION_RATE_LIMIT_MAX_SENDS`.
- **Key rotation:** queued payloads are encrypted using `MODERATION_ENCRYPTION_KEY` or a key derived from `SECRET_KEY`. Rotating either key before clearing/re-encrypting queued rows makes those rows unreadable. The queue can contain message text, recipient and Resend credentials.
- **Privacy:** moderation text is sent to the configured classifier. Logs are hash-only by default, but encrypted queue payloads retain full content and credentials until database cleanup. Hosted endpoints receive user-provided credentials in requests; self-hosted operators control their own processing.
- **Identity assumption:** the legacy password-only web session uses `WEB_MODERATION_USER_ID` (default `0`); configure it consistently. Modern JWT users use their account ID. Other legacy tables remain globally shared.
- **Breaking behavior:** password login and registration now require the current AUP version; older clients receive HTTP 428 until updated. Flutter and Python hold the AUP version independently and must be updated together when the policy changes.
- **Migration:** migration 001 adds columns/tables; the preservation test confirms an existing user row remains. No destructive migration is included. Production Turso migration was not run against a live database.
- **External services:** no real Groq, OpenAI moderation, Resend, Google Maps, OAuth or production database calls were made. Resend idempotency keys are used for queued retries, but only an actual account test can validate full delivery behavior.
- **Admin access:** add user IDs to `MODERATION_ADMIN_USER_IDS` or assign `users.role='admin'`. No new administrator was provisioned.
- **Known project risks:** legacy `SECRET_KEY` fallback remains; the existing app is still monolithic; and the local retry worker is process-based.

## 6. Verification evidence

**Passed:**

- Python moderation and API integration suite: **13 tests passed**.
- Flutter test suite: **8 tests passed**.
- Python `compileall`: passed.
- `git diff --check`: passed before commits.
- Migration test: legacy account row preserved and moderation tables/columns present.
- Direct API test: blocked content sent directly to `/api/send-email` returned HTTP 422 before delivery.

**Not passed / not available:**

- `flutter analyze` crashed in the bundled Dart 3.13.3 analysis server with `SIGBUS`; no analyzer findings were produced. The suite emits the SDK's “running as root” warning in this workspace.
- The initial sandboxed Flutter test invocation could not bind the local test socket; rerunning with the workspace's approved localhost test permission passed.
- No standalone lint tool is configured or installed for Python.
- No live provider or email delivery tests were performed.

Commands used here (the Python dependencies were installed into a temporary `/tmp` virtualenv):

```bash
/tmp/autoreach-step3-venv/bin/python -m unittest discover -s tests -v
/tmp/autoreach-step3-venv/bin/python -m compileall -q app.py auth.py db.py emailer.py followup.py main.py cli autoreach_core moderation tests
git diff --check
cd autoreach_flutter
FLUTTER_SUPPRESS_ANALYTICS=true DASH__SUPPRESS_ANALYTICS=true XDG_CONFIG_HOME=/tmp/autoreach-flutter-config /workspace/scratch/a2be5c0edf75/toolchains/flutter/bin/flutter test
```

For a local checkout with dependencies installed, run:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py auth.py db.py emailer.py followup.py main.py cli autoreach_core moderation tests
cd autoreach_flutter
flutter test
flutter analyze
```

`flutter analyze` should be retried with a functioning Dart analysis server; this workspace's analyzer crashed, so a clean analysis result cannot be claimed.

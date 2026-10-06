# Moderation data and privacy notes

AutoReach checks custom templates and prompts when they are saved, generated messages before displaying or queuing them, and every email immediately before delivery. The moderation provider configured by `MODERATION_PROVIDER` receives the text being checked. With the default `groq` provider, this uses Groq; with `openai`, text is sent to OpenAI's moderation endpoint. Operators must disclose this processing in their privacy notice and select providers/settings appropriate to their users.

`moderation_log` stores a SHA-256 content hash and moderation metadata. It does not store an excerpt by default. `MODERATION_STORE_EXCERPT=true` enables up to 240 characters of excerpt storage; enable it only after updating the public privacy notice and retention policy.

When a provider is unavailable, AutoReach stores the pending item in `moderation_queue` so it can be checked again before delivery. Queue payloads are encrypted using `MODERATION_ENCRYPTION_KEY`, or a key derived from `SECRET_KEY` when no dedicated key is set. The encrypted payload can include message text and delivery credentials needed to retry. Configure a stable secret before deployment and restrict database/backups access. Changing either encryption key makes existing queued payloads unreadable; remove or re-encrypt pending items before rotating it.

Moderation records, blocklist entries, queues, and strikes include `user_id`. The website's legacy password-only session uses `WEB_MODERATION_USER_ID` (default `0`) as its owner identity. Configure that value consistently if the installation needs to map its web session to a real user account.

Required moderation configuration:

- `MODERATION_PROVIDER=groq` (default) or `openai`
- `MODERATION_MODEL=openai/gpt-oss-safeguard-20b` for Groq; model availability is provider-controlled
- `MODERATION_API_KEY`, or provider-specific `GROQ_API_KEY` / `OPENAI_API_KEY`
- `MODERATION_ENCRYPTION_KEY` (recommended for stable queue encryption)
- `MODERATION_STORE_EXCERPT=false` (default)

Queue payloads remain encrypted in the queue table after delivery, cancellation, or resubmission until database cleanup; the current admin UI does not include a queue deletion action. Set an operational retention period and configure database backups accordingly.

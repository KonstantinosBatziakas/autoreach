# ARIA chat proxy

This Vercel function serves the public ARIA chat on `autoreach.dev`. It keeps the support prompt and Groq key on the server, limits requests by client IP, and returns generic errors rather than forwarding provider diagnostics to visitors.

## Environment variables

Configure these in the Vercel project before deploying:

- `GROQ_API_KEY`: server-side Groq API key used by the public ARIA chat.
- `UPSTASH_REDIS_REST_URL`: HTTPS REST URL for an Upstash Redis database.
- `UPSTASH_REDIS_REST_TOKEN`: REST token for that database.
- `ARIA_ALLOWED_ORIGINS` (optional): comma-separated exact origins allowed to call the endpoint. Defaults to `https://autoreach.dev,https://www.autoreach.dev`.

The endpoint fails closed with a generic `503` response when the rate limiter is missing or unavailable. It allows 10 requests per client IP in each 60-second window. The IP is SHA-256 hashed before it is used as a Redis key.

## Local checks

Run the proxy tests with:

```sh
npm test
```

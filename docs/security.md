# Security

Single-user app, but it holds API keys that cost money and a personal database, and it is meant to be reachable
from the internet (Cloud Run). This is the threat model, what is in place, and the checklist for deploying.

## What protects what

| Threat | Defence |
|---|---|
| Strangers using the app | Every `/api` route needs a signed session; the session is only issued after Google confirms a **verified** email equal to `ALLOWED_EMAIL` |
| Forged login cookie | Cookies are signed with `SESSION_SECRET`; the app **refuses to start** if it is missing, shorter than 32 chars, or still the placeholder |
| Reading server files (`.env`, DB, source) | The frontend fallback route only serves files that resolve inside `frontend/dist` (tested with `../`, `%2e%2e`, `..%2f`, and `//` variants); `.env` is also excluded from the Docker image |
| SQL injection | All queries are parameterised; full-text search input is reduced to quoted word tokens before it reaches FTS5 |
| XSS | React escapes all text; a strict CSP allows scripts and styles only from the app itself; external links are restricted to `https://brickset.com/` |
| Clickjacking / MIME sniffing | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff` |
| CSRF | Session cookie is `SameSite=Lax` and `HttpOnly` (`Secure` when `BASE_URL` is https), so cross-site POST/PATCH/DELETE carry no session |
| API discovery | `/docs` and `/openapi.json` are disabled |
| Credentials in logs | Logs are JSON with method, path, status and duration only: no query strings (so no OAuth `code`), cookies or headers. uvicorn's access log is off, and `httpx` request logging is limited to warnings |
| Cross-site logout | `/auth/logout` is `POST` only (the session cookie is `SameSite=Lax`, so other sites cannot send it) |
| Information leaks | Upstream (OpenAI/Brickset) error details are logged server-side only; clients get generic messages |
| Oversized uploads | Voice recordings are capped at 25 MB |
| Prompt injection via Brickset text | The AI agent has one read-only search tool and cannot write; its output is filtered to sets in the local cache and the user picks the final result |
| Stolen/leaked keys in git | `.env`, databases and IDE files are git-ignored; history was scanned for the real key values and known key patterns |
| Container compromise | The image runs as a non-root user; Compose publishes the port on `127.0.0.1` only |
| Vulnerable dependencies | `npm audit` and `pip-audit` were clean at the time of writing |

## Deployment checklist (GCP / Cloud Run)

- Serve over **HTTPS only** and set `BASE_URL` to the `https://` URL; this turns on `Secure` cookies and HSTS.
  Register `https://<your-host>/auth/callback` in the Google OAuth client.
- Put keys in **Secret Manager** and mount them as environment variables; do not bake `.env` into an image.
- Generate a **new** `SESSION_SECRET` for production (`openssl rand -hex 32`); never reuse the dev one.
- Use a **dedicated, restricted OpenAI key** with a monthly spend limit, and a Brickset key used only here.
- Keep the Google OAuth consent screen's user list limited to your account.
- Back up the database (Litestream to a private GCS bucket); keep the bucket private with uniform access control.
- Run with a least-privilege service account (only access to its bucket and secrets).
- Rotate any key that has ever been pasted into a chat, ticket or log.

## Known limitations

- No rate limiting: acceptable for one authenticated user; revisit if more users are ever added.
- Images are hotlinked from Brickset, so their servers see your browser's requests.
- The production Cloud Run configuration (`FORWARDED_ALLOW_IPS=*`, Litestream bucket, secrets) has not been deployed yet.

# TODO: from "runs locally" to "deployed on GCP"

Written for the next working session (human or AI agent). Read first: [README](README.md),
[docs/architecture.md](docs/architecture.md), [docs/security.md](docs/security.md), [docs/plan.md](docs/plan.md).

**State now:** works locally with real Brickset, OpenAI and Google login; 24 backend tests pass; the Docker image builds
and runs (with migrations and Litestream); Phases 0 and 1 are done except the two owner checks below; nothing is deployed.

**Goal:** the app running on Cloud Run behind HTTPS, login limited to one Google account, data durably stored and
backed up, secrets in Secret Manager, deploys automated from GitHub.

## Ground rules for whoever continues
- **Ask the owner before anything with cost, outward effect or hard to reverse**: creating GCP resources, deploying,
  enabling billing, pushing to `main`, rotating or deleting keys. Interactive logins (`gcloud auth login`) are for the
  owner to run with `! <command>`.
- **Never commit or print secrets.** `.env` is git-ignored; verify before every commit (see "Secret hygiene" below).
- Decisions already made, do not re-litigate: SQLite (not Postgres) for v1, Litestream for persistence, Cloud Run with
  a single instance, Google OAuth with one allowed email, **no auth bypass**, images hotlinked, Brickset as the only
  data source, config only via environment variables.
- Keep the owner's style: decide sensible defaults, recommend, keep things simple, do not over-engineer.
- Every change keeps `cd backend && uv run pytest` green and `cd frontend && npm run build` working.

## Gotchas learned the hard way
- **Shell env beats `.env`.** pydantic-settings gives exported environment variables priority over `.env`. A stale
  `OPENAI_API_KEY` in the shell silently overrode the key in `.env` once. When config "doesn't take", check `env`.
- **Cookies are host-bound.** `localhost` and `127.0.0.1` are different sites, which broke the OAuth state check.
  `/auth/login` redirects to the host in `BASE_URL`; always open the app at exactly that address.
- **Google redirect URIs** must match exactly and can take minutes to apply. Prod needs its own
  `https://<host>/auth/callback` registered.
- **`ENTRYPOINT` must pass commands through.** `deploy/entrypoint.sh` once ignored its arguments, so
  `docker compose run app python -m app.seed` silently started the web server and never returned. It now runs any given
  command with `exec "$@"`; with no arguments it starts the app.
- **Docker + non-root + bind mounts:** a host folder is not writable by uid 10001; use the named volume.
- **`docker run --env-file` does not strip inline `# comments`** (Compose does); `.env.example` uses them.
- **Changing `models.py` needs a migration** (`uv run alembic revision --autogenerate -m "..."` in `backend/`); a test
  fails otherwise.
- **`DATABASE_URL` relative paths resolve from the server's working directory.** Starting from `backend/` and from the
  repo root gives two different DB files. In containers use the absolute `sqlite:////data/lego.db`.
- **Brickset** has a daily `getSets` limit (number not published). Every set is cached; the agent is capped by
  `AGENT_MAX_STEPS`. Brickset's `query` rarely matches names a human remembers, hence the theme/year filters.
- **OpenAI model IDs** differ per project. The default `gpt-6-luna` worked for the owner's project; a 403
  `model_not_found` means the key's project lacks access, not that the code is wrong. `TRANSCRIBE_MODEL` default
  (`gpt-4o-transcribe`) is unverified.
- FTS5 is SQLite-specific; moving to Postgres later means reworking `search.py` (e.g. `tsvector`).

## Phase 0: make it real locally (small, do first)
- [x] `docker build -t lego-organizer .` works (it never had been built; it built first time after the Dockerfile rewrite).
- [x] `docker compose up --build` verified (Docker Desktop, Compose v5): starts, `/healthz` 200, `/api` 401, CSP headers,
      seed works, data survives a restart in the `lego-data` volume (file owned by uid 10001).
- [ ] **Owner:** sign in with Google in the container and click through add/edit/delete/search/export (needs your login).
      Tip: port 8000 may be taken by a dev server; stop it first. On Docker Desktop, `docker-credential-desktop` may be
      missing from PATH in non-interactive shells (`/Applications/Docker.app/Contents/Resources/bin`).
- [x] Non-root user (uid 10001) cannot write a host bind mount (`unable to open database file`). Fixed by using a Docker
      named volume (`lego-data`) in `docker-compose.yml`; documented in the README.
- [ ] **Owner:** verify **voice input** end to end in a browser (mic permission, Whisper transcription, CSP allows it).
- [x] Unauthenticated `GET /healthz` (200 only if the DB answers, 503 otherwise), tested.

## Phase 1: code changes needed before deploying
- [x] **Alembic migrations.** Baseline `0001` = the v0.1 schema + FTS5 table; runs on every start; adopts databases made
      by v0.1 with their data. Tests: fresh DB, v0.1 DB adoption, idempotent re-run, and models-vs-migrations drift.
- [x] **Litestream** in the image (pinned 0.5.18, SHA-256 verified per CPU arch), `deploy/litestream.yml`, and
      `deploy/entrypoint.sh` (restore if missing, then `replicate -exec`). Only active when `LITESTREAM_BUCKET` is set.
      Drill passed against a local-folder replica: seed, stop (exit 0), delete the data volume, start fresh: all items, FTS
      search and migration version came back. **Not tested against real GCS** (needs the bucket from Phase 2).
- [x] Cloud Run settings decided and documented in `docs/architecture.md`: `--max-instances=1`, `--no-cpu-throttling`.
- [x] Structured JSON logging; request lines carry no query string, cookies or headers (tested). uvicorn's access log is
      off; `httpx` and `alembic` are quiet.
- [x] `POST /auth/logout` (204) with a button in the UI; GET is gone (tested).
- [x] Docker base images pinned: `node:22.23.4-bookworm-slim`, `python:3.12.16-slim-bookworm`, `uv:0.13.7`.
- [x] `--forwarded-allow-ips='*'` removed from the image: uvicorn now reads `FORWARDED_ALLOW_IPS` (default 127.0.0.1),
      which only the Cloud Run deploy sets to `*`.

## Phase 2: GCP setup (owner approves each step)
- [ ] Create/choose a GCP project and billing account; set a **budget alert** (e.g. low monthly cap).
- [ ] Enable APIs: Cloud Run, Artifact Registry, Secret Manager, Cloud Storage, Cloud Build (if used).
- [ ] Artifact Registry Docker repo; private GCS bucket for Litestream (uniform bucket-level access, versioning on,
      public access prevention on).
- [ ] Dedicated **runtime service account** with only: read secrets it needs, read/write that one bucket.
- [ ] Secret Manager entries: `BRICKSET_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
      `SESSION_SECRET` (**generate a new one**, `openssl rand -hex 32`), `ALLOWED_EMAIL`. Mount as env vars.
- [ ] Use a **separate, restricted OpenAI key with a monthly spend limit** for production.
- [ ] Deploy to Cloud Run (region near the owner), `BASE_URL=https://<service-url>`, ingress all, unauthenticated
      invocation allowed (the app does its own Google login).
- [ ] Google Cloud Console: add the prod redirect URI `https://<host>/auth/callback`; keep the consent screen's test
      users limited to the owner. Optional: custom domain (Cloud Run domain mapping or load balancer) and update
      `BASE_URL` and the redirect URI to match.

## Phase 3: CI/CD (GitHub Actions)
- [ ] CI on every push/PR: `uv run pytest`, `npm ci && npm run build`, `npm audit --omit=dev`, `pip-audit`, and a
      secret scanner (gitleaks).
- [ ] Deploy workflow on tag or manual trigger: build image, push to Artifact Registry, `gcloud run deploy`.
- [ ] Authenticate GitHub to GCP with **Workload Identity Federation**, not a downloaded service-account JSON key.
- [ ] Branch protection on `main` (require CI).

## Phase 4: verify production
- [ ] Sign in with the allowed account works; a different Google account is rejected with the friendly message.
- [ ] Unauthenticated `curl` to `/api/items` is 401; `/docs` and `/openapi.json` are not exposed.
- [ ] Re-run the path-traversal attack against the deployed URL using raw paths (`curl --path-as-is
      "$URL/%2e%2e/%2e%2e/etc/passwd"`) and confirm only the SPA shell comes back. Check response headers (CSP, HSTS,
      `X-Frame-Options`).
- [ ] **Persistence drill:** add an item, deploy a new revision (or force a restart), confirm the item is still there.
- [ ] **Restore drill:** delete the local DB, start from the bucket replica only, confirm data and search come back.
- [ ] Confirm secrets are not in the image (`docker history`, no `.env`) or in Cloud Run's plain-text env config.
- [ ] Update README "Status", `docs/architecture.md` (deployment diagram, Litestream) and `docs/security.md`.

## Phase 5: product backlog (optional, after deployment)
- [ ] **Bulk import**: paste a list of set numbers (with an optional box) and review matches before saving.
- [ ] Respect Brickset limits visibly: show a clear message on "API limit exceeded", and backfill gently.
- [ ] Download and store images (GCS) instead of hotlinking, so the catalog survives dead links.
- [ ] Pagination or virtual scrolling for large collections; duplicate warning when adding a set that is already owned.
- [ ] Per-box page with print-friendly contents list (the owner skipped labels, but a printable list may help).
- [ ] Frontend tests (Vitest/Playwright for the add flow) and an accessibility pass; dark-mode polish.
- [ ] Optional price tracking, minifig/part inventories (Rebrickable), quantity or condition fields.

## Secret hygiene (run before every commit)
```bash
git ls-files | grep -E '(^|/)\.env$|\.db|\.idea|settings\.local' || echo clean   # nothing sensitive tracked
git grep -nIE 'sk-[A-Za-z0-9_-]{16,}|GOCSPX-|AIza[0-9A-Za-z_-]{30,}|BEGIN [A-Z ]*PRIVATE KEY' || echo no-key-patterns
```
If a key ever leaks (git history, chat, logs): **rotate it at the provider first**, then clean up.

## Small tech debt
- [ ] `pytest-asyncio` warns that `asyncio_default_fixture_loop_scope` is unset; set it in `pyproject.toml`.
- [ ] Add lint/format config (ruff for Python; oxlint is already scaffolded for the frontend) and run it in CI.
- [ ] No rate limiting; acceptable for one user, revisit if that ever changes.

# TODO: from "runs locally" to "deployed on GCP"

Written for the next working session (human or AI agent). Read first: [README](README.md),
[docs/architecture.md](docs/architecture.md), [docs/security.md](docs/security.md), [docs/plan.md](docs/plan.md).

**State now:** works locally with real Brickset, OpenAI and Google login; 24 backend tests pass; the Docker image builds
and runs (with migrations and Litestream). Phases 0, 1 and the code side of 3 are done; Phase 2 is scripted and waits for
the owner's GCP account. **Next: follow [docs/deploy.md](docs/deploy.md).** Nothing is deployed yet.

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
      search and migration version came back. The production config uses `gs://` (not `gcs://`, which Litestream rejects);
      it parses and reaches the GCS client, then fails only for lack of credentials. **Not tested against real GCS**
      (needs the bucket and service account from Phase 2); the container refuses to start without working credentials.
- [x] Cloud Run settings decided and documented in `docs/architecture.md`: `--max-instances=1`, `--no-cpu-throttling`.
- [x] Structured JSON logging; request lines carry no query string, cookies or headers (tested). uvicorn's access log is
      off; `httpx` and `alembic` are quiet.
- [x] `POST /auth/logout` (204) with a button in the UI; GET is gone (tested).
- [x] Docker base images pinned: `node:22.23.4-bookworm-slim`, `python:3.12.16-slim-bookworm`, `uv:0.13.7`.
- [x] `--forwarded-allow-ips='*'` removed from the image: uvicorn now reads `FORWARDED_ALLOW_IPS` (default 127.0.0.1),
      which only the Cloud Run deploy sets to `*`.

## Phase 2: GCP setup (owner approves each step)
Everything below is scripted in `deploy/setup-gcp.sh` (re-runnable, confirms each stage, dry-run with `DRY_RUN=1`).
Follow [docs/deploy.md](docs/deploy.md). **Status: written and dry-run, not yet run for real; waiting for the owner.**
- [ ] Project, billing account and a **budget alert** (stage 3).
- [ ] Enable APIs (stage 4).
- [ ] Artifact Registry repo and the private, versioned backup bucket (stage 5).
- [ ] Runtime service account (6 secrets + that one bucket only) and a deployer account (stage 6).
- [ ] Secret Manager: the 6 values; a **new** `SESSION_SECRET`; a **separate OpenAI key with a monthly spend limit** (stage 7).
- [ ] Deploy to Cloud Run: done by the Deploy workflow (phase 3). Region default `europe-west1`; `BASE_URL` is the
      deterministic `https://lego-organizer-<project number>.<region>.run.app`, to be confirmed after the first deploy.
- [ ] Add the prod redirect URI `<BASE_URL>/auth/callback` in the Google console (manual, stage 9).
- Skipped for now: custom domain (no domain yet; later update `BASE_URL` and the redirect URI).

## Phase 3: CI/CD (GitHub Actions)
- [x] `.github/workflows/ci.yml` on every push to `main` and every PR: ruff, pytest, `pip-audit`, oxlint, frontend build,
      `npm audit --omit=dev`, gitleaks over the full history, and a Docker build with a smoke test (command passthrough,
      `/healthz`, `/api` 401). Actions are pinned to commit SHAs. Each check was run locally; **not yet run on GitHub**.
- [x] `.github/workflows/deploy.yml`: manual or on a `v*` tag, only from `main`/tags; runs CI first, builds and pushes
      the image, `gcloud run deploy` (1 instance, CPU always on, secrets from Secret Manager, `/healthz` probe), then
      checks the live URL. Linted with actionlint; **never run**.
- [x] GitHub to GCP with **Workload Identity Federation** (no JSON key), limited to this repository (created by the
      setup script, stage 8).
- [ ] **Owner:** branch protection on `main` requiring the 4 CI jobs. May be unavailable on a private repo with a free
      GitHub plan (see docs/deploy.md section 5).

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
- [x] `pytest-asyncio` loop scope set in `pyproject.toml`.
- [x] Lint config: ruff (Python, `pyproject.toml`) and oxlint (frontend), both run in CI. oxlint has 2 existing warnings
      (`ui.tsx`, `Collection.tsx`) that do not fail the build.
- [ ] No rate limiting; acceptable for one user, revisit if that ever changes.

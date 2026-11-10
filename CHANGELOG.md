# Changelog

Timestamped, newest first (local time, from git history). Add an entry with every commit.

## 2026-11-10
- Added this changelog (project rule in `.claude/CLAUDE.md`).
- Audit of the deployment work against `TODO.md`: ruff clean, 24 backend tests pass, frontend builds, `ci.yml` exposes
  `workflow_call` so `deploy.yml` can reuse it, `setup-gcp.sh` passes `bash -n` and a dry run. Remaining open items in
  `TODO.md` all need the owner (GCP account, Google console, GitHub settings, browser checks).

## 2026-11-09
- 15:33 Phase 3: CI workflow (ruff, pytest, pip-audit, oxlint, build, npm audit, gitleaks, Docker smoke test), keyless
  deploy workflow (Workload Identity Federation), `deploy/setup-gcp.sh`, `docs/deploy.md`.
- 15:19 Litestream: use the `gs://` scheme (`gcs://` is rejected).
- 15:17 Entrypoint: run a given command instead of always starting the server.
- 15:16 TODO: Docker Compose verified on Docker Desktop.
- 15:01 Phases 0-1: Alembic migrations, Litestream backup, `/healthz`, JSON logs, POST logout, pinned images.

## 2026-11-08
- 18:28 Added `TODO.md`: roadmap from local v0.1 to a GCP deployment.
- 18:15 Lego Organizer v0.1.

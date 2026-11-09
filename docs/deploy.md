# Deploy guide: from this repo to Cloud Run

Written for the first deployment. Follow it top to bottom; it should take about an hour, most of it waiting for
consoles and builds. Everything that could be prepared without your Google/GitHub accounts is already in the repo;
this guide covers what only you can do.

**What you will end up with:** the app at `https://lego-organizer-<number>.<region>.run.app`, login limited to your
Google account, the database continuously backed up to a private bucket, secrets in Secret Manager, and a GitHub
"Deploy" button that ships `main` without any downloaded key files.

## What is ready, and what is not tested

| Ready in the repo | Tested how |
|---|---|
| Docker image with migrations, Litestream, `/healthz`, JSON logs | Built and run locally; full backup-and-restore drill against a local-folder replica |
| `.github/workflows/ci.yml` (lint, tests, audits, secret scan, image smoke test) | Each check run locally; workflow files linted with `actionlint`. **Never run on GitHub yet** |
| `.github/workflows/deploy.yml` (build, push, deploy, live check) | Linted only. **Never run** |
| `deploy/setup-gcp.sh` (creates all of GCP for you) | Shellchecked and dry-run (prints every command, changes nothing). **Never run for real** |

So expect small surprises on the first real run (a flag that changed, a permission that needs a minute to
propagate). The troubleshooting table at the end lists the likely ones.

## 0. What you need before you start

- [ ] A **Google account with a billing method** (card) for Google Cloud. New accounts usually get free credit.
- [ ] **gcloud CLI**: `brew install --cask gcloud-cli`, then `gcloud --version`.
- [ ] **A new OpenAI API key for production**, in an OpenAI project with a **monthly spend limit** (set the limit
      in OpenAI's dashboard under the project's limits/budget). Do not reuse the one in `.env`.
- [ ] Your existing **Brickset key**, **Google OAuth client** (ID and secret) and **allowed email**: the script can
      read them from your local `.env`, so run it from this checkout.
- [ ] Optional: **GitHub CLI** (`brew install gh && gh auth login`) lets the script set the GitHub variables for you.
      Without it, you paste 7 values into GitHub's web page.
- [ ] Your Google OAuth client must belong to a project where you can edit it (you will add one redirect URI).

No domain name is needed: Cloud Run provides the HTTPS address.

## 1. Get the code onto `main` (you do this; the project rule is that I never merge)

1. Push the branch: `git push -u origin mkv/iteration2`.
2. Open a pull request into `main` on GitHub. **This is the first time CI runs** (4 jobs: backend, frontend, secrets,
   docker). If something is red, tell me what the log says and I will fix it.
3. When it is green, merge it yourself.

The Deploy workflow only appears in GitHub's Actions tab once it is on `main`, and it refuses to deploy any other
branch.

## 2. Create everything in Google Cloud (one script)

```bash
./deploy/setup-gcp.sh
```

Optional first look without changing anything: `DRY_RUN=1 ./deploy/setup-gcp.sh`.

It walks through 9 stages, shows every command before it runs it, asks you to confirm before creating anything, and
can be re-run safely if it stops halfway (finished steps are skipped; your non-secret answers are remembered in
`deploy/.setup.env`, which is git-ignored).

| Stage | What happens | Needs you |
|---|---|---|
| 1 Prerequisites | Checks gcloud and logs you in | Browser sign-in |
| 2 Choices | Project id, region (`europe-west1`), GitHub repo, billing account | Accept defaults or type |
| 3 Project, billing, **budget alert** | Creates the project, links billing, adds a monthly budget with email alerts | Amount (default 5) and currency |
| 4 APIs | Turns on the Google services needed | - |
| 5 Registry and bucket | Docker image repository; private backup bucket (versioned, no public access) | - |
| 6 Service accounts | One identity for the app (secrets + that one bucket only), one for GitHub (deploy only) | - |
| 7 Secrets | Stores the 6 values in Secret Manager; makes a **fresh** `SESSION_SECRET` | Paste the new OpenAI key; answer Y to reuse the others from `.env` |
| 8 Keyless GitHub login | Workload Identity Federation limited to *your* repo | - |
| 9 Redirect URI and GitHub variables | Prints the app's address and the 7 GitHub variables | **Manual step in the Google console (below)** |

**The manual step in stage 9.** Google must be told the new address may receive sign-ins:

1. Open <https://console.cloud.google.com/auth/clients> in the Google Cloud project that owns your OAuth client.
   If that page looks different: *APIs & Services → Credentials → your OAuth 2.0 Web client*.
2. Under **Authorized redirect URIs** click *Add URI* and enter exactly what the script prints, e.g.
   `https://lego-organizer-123456789012.europe-west1.run.app/auth/callback`. Keep the `localhost` one.
3. Save. It can take a few minutes to apply.
4. Keep the consent screen in **Testing** with only your own email as a test user.

The 7 GitHub variables (not secrets; none is sensitive) are `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WIF_PROVIDER`,
`GCP_DEPLOY_SA`, `GCP_RUNTIME_SA`, `GCP_BUCKET`, `BASE_URL`. With `gh` the script sets them; otherwise add them at
*GitHub → repo → Settings → Secrets and variables → Actions → Variables → New repository variable*.

## 3. Deploy

GitHub → **Actions → Deploy → Run workflow** → branch `main`. (Later: `git tag v0.2.0 && git push --tags` also deploys.)

It re-runs the CI checks, builds the image, pushes it to Artifact Registry, deploys Cloud Run with: 1 instance maximum,
CPU always on (so backups keep flowing), the 6 secrets mounted as environment variables, and a `/healthz` startup
probe. The last step checks `/healthz` returns 200 and `/api/items` returns 401 on the live URL.

The log prints `Service URL: https://...`. **Compare it with `BASE_URL`.** If they differ, change the `BASE_URL`
variable and the Google redirect URI to the real address, then run Deploy again.

## 4. Verify production (this is TODO Phase 4)

Set `URL` to the service URL, then:

```bash
URL=https://lego-organizer-XXXX.europe-west1.run.app
curl -s $URL/healthz                                   # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" $URL/api/items   # 401
curl -s -o /dev/null -w "%{http_code}\n" $URL/openapi.json  # no API description: the app's HTML shell (200) or 404, never JSON
curl -sI $URL | grep -iE 'strict-transport|content-security|x-frame'    # all three present
curl -s --path-as-is "$URL/%2e%2e/%2e%2e/etc/passwd" | head -c 100     # the HTML shell, never file contents
```

Then in the browser:

- [ ] Sign in with your allowed account: works.
- [ ] Sign in with a different Google account: rejected with the friendly message.
- [ ] Add an item, edit it, search for it.
- [ ] **Backup check:** `gcloud storage ls -r gs://<GCP_BUCKET> | head` shows files under `lego.db/`.
- [ ] **Persistence / restore drill:** run Deploy again (or `gcloud run services update lego-organizer --region
      <region> --update-env-vars DRILL=$(date +%s)`). A new revision starts with an *empty* disk and must restore from
      the bucket. Reload: your item and search must still be there. This is the real restore test.
- [ ] Secrets are not in the image or plain config: `gcloud run services describe lego-organizer --region <region>`
      shows `secretKeyRef` entries, not values.
- [ ] Logs are JSON and contain no cookies or `code=` strings:
      `gcloud run services logs read lego-organizer --region <region> --limit 30`.

Then tell me the results and I will update the README, `docs/architecture.md` and `docs/security.md`.

## 5. Protect `main` (GitHub setting, only you can do it)

*Settings → Branches → Add branch ruleset / protection rule* for `main`: require status checks to pass
(`backend`, `frontend`, `secrets`, `docker`; they only appear in the list after CI has run once) and block force
pushes. **Caveat:** on a *private* repository with GitHub's free plan, branch protection is not available; check
*Settings → Branches*. If it is greyed out, the alternatives are making the repository public (it contains no secrets;
CI scans for that) or just relying on the habit of merging only green pull requests.

## Costs and safety

- The budget alert from stage 3 emails you at 50%, 90% and 100% of the monthly amount. It **warns, it does not stop
  spending**. After the first week, look at *Billing → Reports* once.
- For one user the expected bill is small: Cloud Run bills only while an instance is up (it scales to zero when
  idle), storage is a few megabytes. The OpenAI key's own spend limit caps the AI features.
- To switch everything off: `gcloud run services delete lego-organizer --region <region>`; to remove the project
  entirely, `gcloud projects delete <project-id>` (30-day recovery window).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Setup script: "Permission denied" creating the budget | Needs billing-admin rights. The script falls back to a console link; create the budget there |
| Setup script: IAM binding says service account does not exist | IAM lag; wait a minute and re-run the script (it skips finished work) |
| Deploy: `unauthorized_client` / "could not exchange token" | `GCP_WIF_PROVIDER` or `GCP_DEPLOY_SA` variable is wrong or missing; or the repo name in stage 2 differs from the real one (case matters) |
| Deploy: "Permission denied on secret ... for Revision service account" | Re-run the script (stage 7 grants the runtime account access) |
| Deploy: "Revision ... failed to start" / startup probe failed | Read the logs: `gcloud run services logs read lego-organizer --region <region> --limit 50`. Usual causes: Litestream cannot reach the bucket (runtime account lacks `storage.objectAdmin` on it) or a missing secret value |
| Deploy: "One or more users named in the policy do not belong to a permitted customer" | An organisation policy forbids public access (work/school Google account). Use a personal project |
| Sign-in: `redirect_uri_mismatch` | The redirect URI in the Google console must equal `BASE_URL + /auth/callback` exactly (https, no trailing slash); wait a few minutes after saving |
| Sign-in loops or lands on `localhost` | `BASE_URL` variable is wrong; fix it and run Deploy again |
| Sign-in says "not allowed" | The `allowed-email` secret differs from the account you used (compare, including case), or the Google email is unverified |
| Container exits at start with a Litestream credentials error | Intended: it refuses to run without a working backup. Fix the bucket permission, do not remove `LITESTREAM_BUCKET` |
| CI red on `secrets` job | gitleaks found something that looks like a key. Rotate it at the provider first, then tell me |
| Actions tab has no "Deploy" | The workflow is not on `main` yet; merge the pull request |

## After the first deploy: normal life

- **Ship a change:** pull request → CI green → merge → Actions → Deploy (or push a `v*` tag).
- **Roll back:** Cloud Run console → the service → *Revisions* → send 100% traffic to the previous revision. (Data is
  independent of revisions.) Database schema changes only move forward, so ask me before rolling back across a
  migration.
- **Change a secret:** `printf %s 'new-value' | gcloud secrets versions add <name> --data-file=-`, then run Deploy again.
- **See the data:** use the in-app CSV/JSON export, or restore the replica locally with `litestream restore`.

#!/usr/bin/env bash
# Guided, re-runnable GCP setup for Lego Organizer (TODO Phase 2). Run it yourself, in a terminal:
#
#     ./deploy/setup-gcp.sh
#
# It creates NOTHING until you confirm each stage, prints every gcloud command before running it, skips what already
# exists (safe to re-run after an interruption) and never prints or stores secret values (they go to Secret Manager
# over stdin). Non-secret choices are remembered in deploy/.setup.env (git-ignored).
#
#     DRY_RUN=1 ./deploy/setup-gcp.sh        print the commands only; change nothing
#     NONINTERACTIVE=1 DRY_RUN=1 ...         additionally accept all defaults (used to test the script itself)
set -euo pipefail
cd "$(dirname "$0")/.."

STATE=deploy/.setup.env
DRY_RUN="${DRY_RUN:-0}"
NONINTERACTIVE="${NONINTERACTIVE:-0}"
TOTAL=9
N=0

# ---------------------------------------------------------------- helpers
say()  { printf '%s\n' "$*"; }
stage() { N=$((N + 1)); printf '\n\033[1m━━ Stage %d/%d: %s ━━\033[0m\n' "$N" "$TOTAL" "$1"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

pause() { [[ $NONINTERACTIVE = 1 ]] && return 0; read -r -p "Press Enter to continue… " _; }

confirm() { # confirm "question"  (anything but y/Y stops the script; progress is kept)
  [[ $NONINTERACTIVE = 1 ]] && { say "$1 [auto-yes]"; return 0; }
  local a; read -r -p "$1 [y/N] " a
  [[ $a =~ ^[Yy] ]] || { say "Stopped here. Re-run ./deploy/setup-gcp.sh later; finished steps are skipped."; exit 0; }
}

ask() { # ask VAR "prompt" [default]
  local v=""
  if [[ $NONINTERACTIVE = 1 ]]; then v="${3:-}"; else read -r -p "$2${3:+ [$3]}: " v; fi
  printf -v "$1" '%s' "${v:-${3:-}}"
}

ask_secret() { # ask_secret VAR "prompt"   (typed input is hidden)
  local v=""
  if [[ $NONINTERACTIVE = 1 ]]; then v="dummy-secret"; else read -r -s -p "$2: " v; echo; fi
  printf -v "$1" '%s' "$v"
}

run() { printf '  \033[2m$ %s\033[0m\n' "$*" >&2; [[ $DRY_RUN = 1 ]] || "$@"; }   # the echo goes to stderr so '>/dev/null' only hides gcloud's output

exists() { [[ $DRY_RUN = 1 ]] && return 1; "$@" >/dev/null 2>&1; }   # "does it already exist?" (dry run: pretend no)
has_output() { [[ $DRY_RUN = 1 ]] && return 1; [[ -n "$("$@" 2>/dev/null)" ]]; }   # for list commands, which succeed even when empty

open_url() {
  say "  → $1"
  [[ $NONINTERACTIVE = 1 ]] && return 0
  if command -v open >/dev/null 2>&1; then open "$1" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1 || true
  fi
}

save() { # save VAR  – remember a non-secret value for the next run
  touch "$STATE"
  grep -v "^$1=" "$STATE" > "$STATE.tmp" || true
  printf '%s=%q\n' "$1" "${!1}" >> "$STATE.tmp"
  mv "$STATE.tmp" "$STATE"
}

env_val() { # env_val KEY  – read a value from the local .env without echoing it (empty if missing)
  [[ -f .env ]] || return 0
  grep -E "^$1=" .env | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^["'\'']//; s/["'\'']$//' || true
}

put_secret() { # put_secret name value  – create the secret, or add a version after asking
  local name=$1 value=$2
  if exists gcloud secrets describe "$name" --project "$PROJECT_ID"; then
    local a="n"
    [[ $NONINTERACTIVE = 1 ]] || read -r -p "  secret $name already exists. Add a NEW version from what you just entered? [y/N] " a
    [[ $a =~ ^[Yy] ]] || { say "  kept existing $name"; return 0; }
    printf '  \033[2m$ gcloud secrets versions add %s --data-file=-  (value hidden)\033[0m\n' "$name"
    [[ $DRY_RUN = 1 ]] || printf '%s' "$value" | gcloud secrets versions add "$name" --project "$PROJECT_ID" --data-file=- >/dev/null
  else
    printf '  \033[2m$ gcloud secrets create %s --data-file=-  (value hidden)\033[0m\n' "$name"
    [[ $DRY_RUN = 1 ]] || printf '%s' "$value" | gcloud secrets create "$name" --project "$PROJECT_ID" --replication-policy=automatic --data-file=- >/dev/null
  fi
  run gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT_ID" \
    --member "serviceAccount:$RUNTIME_SA" --role roles/secretmanager.secretAccessor --quiet >/dev/null
}

secret_from_env_or_ask() { # secret_from_env_or_ask secret-name ENV_KEY "prompt"
  local name=$1 key=$2 prompt=$3 value
  value="$(env_val "$key")"
  if [[ -n $value && $NONINTERACTIVE != 1 ]]; then
    local a; read -r -p "  Use $key from your local .env for $name? [Y/n] " a
    [[ $a =~ ^[Nn] ]] && value=""
  fi
  if [[ -z $value ]]; then ask_secret value "  $prompt"; fi
  [[ -n $value ]] || die "Empty value for $name."
  put_secret "$name" "$value"
}

# shellcheck source=/dev/null
[[ -f $STATE ]] && source "$STATE"

# ---------------------------------------------------------------- 1. prerequisites
stage "Prerequisites"
say "This sets up Google Cloud for Lego Organizer: project, bucket for backups, Artifact Registry, secrets,"
say "service accounts and keyless GitHub deployment. Cost for one user is a few cents a month; the budget alert in"
say "stage 3 guards against surprises."
[[ $DRY_RUN = 1 ]] && say "(DRY RUN: commands are printed, nothing is executed.)"
if ! command -v gcloud >/dev/null 2>&1 && [[ $DRY_RUN != 1 ]]; then
  say "The gcloud CLI is not installed. On macOS:  brew install --cask gcloud-cli   (or see https://cloud.google.com/sdk/docs/install)"
  die "Install it, then re-run this script."
fi
if [[ $DRY_RUN != 1 ]]; then
  ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
  if [[ -z $ACCOUNT ]]; then
    say "You are not logged in to gcloud. A browser window will open; sign in with the Google account that will own the project."
    confirm "Run 'gcloud auth login' now?"
    gcloud auth login
    ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"
  fi
  say "gcloud is logged in as: $ACCOUNT"
fi
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  HAVE_GH=1; say "GitHub CLI: available (stage 9 can set the repository variables for you)."
else
  HAVE_GH=0; say "GitHub CLI: not available/logged in (stage 9 will show the values to paste in the GitHub web UI instead)."
fi

# ---------------------------------------------------------------- 2. choices
stage "Your choices (nothing is created yet)"
remote="$(git remote get-url origin 2>/dev/null | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##' || true)"
ask PROJECT_ID  "GCP project id (globally unique, lowercase)" "${PROJECT_ID:-lego-organizer-$(openssl rand -hex 2)}"
ask REGION      "Region (europe-west1 = Belgium, cheap Tier-1 pricing)" "${REGION:-europe-west1}"
ask GITHUB_REPO "GitHub repository (owner/name)" "${GITHUB_REPO:-$remote}"
[[ -n $GITHUB_REPO ]] || die "GitHub repository is required (workload identity is limited to it)."
if [[ -z ${BILLING_ACCOUNT:-} ]]; then
  if [[ $DRY_RUN = 1 ]]; then
    BILLING_ACCOUNT="AAAAAA-BBBBBB-CCCCCC"
  else
    say "Billing accounts you can use:"
    gcloud billing accounts list --filter=open=true --format='table(name.basename(),displayName)' || true
    ask BILLING_ACCOUNT "Billing account id (like 01ABCD-234567-89EFGH)" ""
    [[ -n $BILLING_ACCOUNT ]] || die "No billing account. Create one at https://console.cloud.google.com/billing and re-run."
  fi
fi
SERVICE=lego-organizer
BUCKET="${PROJECT_ID}-litestream"
RUNTIME_SA_NAME=lego-runtime
DEPLOY_SA_NAME=lego-deployer
RUNTIME_SA="$RUNTIME_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
DEPLOY_SA="$DEPLOY_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
for v in PROJECT_ID REGION GITHUB_REPO BILLING_ACCOUNT; do save "$v"; done
say ""
say "  project        $PROJECT_ID"
say "  region         $REGION"
say "  GitHub repo    $GITHUB_REPO"
say "  billing        $BILLING_ACCOUNT"
say "  backup bucket  gs://$BUCKET"
confirm "Create/configure all of this as described?"

# ---------------------------------------------------------------- 3. project, billing, budget
stage "Project, billing and budget alert"
if exists gcloud projects describe "$PROJECT_ID"; then say "  project $PROJECT_ID already exists"; else run gcloud projects create "$PROJECT_ID" --name "Lego Organizer"; fi
run gcloud billing projects link "$PROJECT_ID" --billing-account "$BILLING_ACCOUNT"
if [[ $DRY_RUN = 1 ]]; then PROJECT_NUMBER=123456789012
else PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"; fi
save PROJECT_NUMBER
say ""
say "Budget alert: emails you when spending passes 50%, 90% and 100% of a monthly amount. Use your billing"
say "account's currency. (An alert does not stop spending; it warns you.)"
ask BUDGET_AMOUNT   "Monthly budget amount" "5"
ask BUDGET_CURRENCY "Currency code" "EUR"
run gcloud services enable billingbudgets.googleapis.com --project "$PROJECT_ID"
if ! has_output gcloud billing budgets list --billing-account "$BILLING_ACCOUNT" --filter="displayName=lego-organizer" --format='value(name)'; then
  if ! run gcloud billing budgets create --billing-account "$BILLING_ACCOUNT" --display-name lego-organizer \
      --budget-amount "${BUDGET_AMOUNT}${BUDGET_CURRENCY}" --filter-projects "projects/$PROJECT_NUMBER" \
      --threshold-rule percent=0.5 --threshold-rule percent=0.9 --threshold-rule percent=1.0; then
    say "  Could not create the budget from the CLI (it needs billing-admin rights). Create it by hand instead:"
    open_url "https://console.cloud.google.com/billing/$BILLING_ACCOUNT/budgets?project=$PROJECT_ID"
    pause
  fi
else
  say "  budget 'lego-organizer' already exists"
fi

# ---------------------------------------------------------------- 4. APIs
stage "Enable APIs"
run gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  cloudresourcemanager.googleapis.com --project "$PROJECT_ID"

# ---------------------------------------------------------------- 5. registry and bucket
stage "Image registry and backup bucket"
if exists gcloud artifacts repositories describe lego --location "$REGION" --project "$PROJECT_ID"; then
  say "  Artifact Registry repo 'lego' already exists"
else
  run gcloud artifacts repositories create lego --repository-format docker --location "$REGION" \
    --description "Lego Organizer images" --project "$PROJECT_ID"
fi
if exists gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID"; then
  say "  bucket gs://$BUCKET already exists"
else
  run gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT_ID" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi
run gcloud storage buckets update "gs://$BUCKET" --versioning --project "$PROJECT_ID"
# Versioning keeps deleted/overwritten backup files as a safety net; expire them after 30 days so they don't pile up.
LIFECYCLE="$(mktemp)"
printf '{"rule":[{"action":{"type":"Delete"},"condition":{"daysSinceNoncurrentTime":30,"isLive":false}}]}\n' > "$LIFECYCLE"
run gcloud storage buckets update "gs://$BUCKET" --lifecycle-file "$LIFECYCLE" --project "$PROJECT_ID"
rm -f "$LIFECYCLE"

# ---------------------------------------------------------------- 6. service accounts
stage "Service accounts (least privilege)"
say "  runtime  ($RUNTIME_SA): what the running app uses. Reads its 6 secrets, writes ONLY the backup bucket."
say "  deployer ($DEPLOY_SA): what GitHub Actions uses. Deploys Cloud Run and pushes images; holds no key file."
for sa in "$RUNTIME_SA_NAME:Lego Organizer runtime" "$DEPLOY_SA_NAME:Lego Organizer GitHub deployer"; do
  name="${sa%%:*}"; display="${sa#*:}"
  if exists gcloud iam service-accounts describe "$name@$PROJECT_ID.iam.gserviceaccount.com" --project "$PROJECT_ID"; then
    say "  $name already exists"
  else
    run gcloud iam service-accounts create "$name" --display-name "$display" --project "$PROJECT_ID"
  fi
done
say "  (new service accounts can take a few seconds to become visible to IAM)"; [[ $DRY_RUN = 1 ]] || sleep 10
run gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$RUNTIME_SA" \
  --role roles/storage.objectAdmin --project "$PROJECT_ID" --quiet >/dev/null
run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$DEPLOY_SA" --role roles/run.admin --quiet >/dev/null
run gcloud artifacts repositories add-iam-policy-binding lego --location "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:$DEPLOY_SA" --role roles/artifactregistry.writer --quiet >/dev/null
run gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" --project "$PROJECT_ID" \
  --member "serviceAccount:$DEPLOY_SA" --role roles/iam.serviceAccountUser --quiet >/dev/null

# ---------------------------------------------------------------- 7. secrets
stage "Secrets (Secret Manager)"
say "Values go straight to Secret Manager and are never printed. Typed input is hidden."
say ""
say "• OpenAI: use a NEW key just for production, in a project with a monthly spend limit."
say "  Create it here (I could not verify the current layout; look for API keys and the project's limits/budget):"
open_url "https://platform.openai.com/api-keys"
say ""
secret_from_env_or_ask brickset-api-key      BRICKSET_API_KEY      "Brickset API key"
# Deliberately never offered from .env: production gets its own restricted key with a spend limit.
ask_secret OPENAI_PROD_KEY "  OpenAI production API key (the NEW restricted one)"
[[ -n $OPENAI_PROD_KEY ]] || die "Empty value for openai-api-key."
put_secret openai-api-key "$OPENAI_PROD_KEY"
unset OPENAI_PROD_KEY
secret_from_env_or_ask google-client-id      GOOGLE_CLIENT_ID      "Google OAuth client ID"
secret_from_env_or_ask google-client-secret  GOOGLE_CLIENT_SECRET  "Google OAuth client secret"
secret_from_env_or_ask allowed-email         ALLOWED_EMAIL         "The ONE Google email allowed to sign in"
if exists gcloud secrets describe session-secret --project "$PROJECT_ID"; then
  say "  session-secret already exists (kept; rotating it would sign you out)"
else
  put_secret session-secret "$(openssl rand -hex 32)"   # a fresh production value, never the dev one
fi

# ---------------------------------------------------------------- 8. workload identity federation
stage "Keyless GitHub → Google login (Workload Identity Federation)"
say "GitHub Actions proves who it is with a short-lived token; Google trusts only repo '$GITHUB_REPO'. No JSON key exists."
if exists gcloud iam workload-identity-pools describe github --location global --project "$PROJECT_ID"; then
  say "  pool 'github' already exists"
else
  run gcloud iam workload-identity-pools create github --location global --display-name "GitHub Actions" --project "$PROJECT_ID"
fi
if exists gcloud iam workload-identity-pools providers describe github-actions --location global \
    --workload-identity-pool github --project "$PROJECT_ID"; then
  say "  provider 'github-actions' already exists"
else
  run gcloud iam workload-identity-pools providers create-oidc github-actions --location global \
    --workload-identity-pool github --project "$PROJECT_ID" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition "assertion.repository=='$GITHUB_REPO'"
fi
run gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" --project "$PROJECT_ID" --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GITHUB_REPO" >/dev/null
if [[ $DRY_RUN = 1 ]]; then WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github-actions"
else WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe github-actions --location global \
  --workload-identity-pool github --project "$PROJECT_ID" --format='value(name)')"; fi

# ---------------------------------------------------------------- 9. Google sign-in redirect + GitHub variables
stage "Google sign-in redirect and GitHub variables"
BASE_URL="https://$SERVICE-$PROJECT_NUMBER.$REGION.run.app"
say "The app's address will be (Cloud Run's standard format, confirmed after the first deploy):"
say "    $BASE_URL"
say ""
say "MANUAL STEP – tell Google this address is allowed to receive sign-ins. In the Google Cloud project that owns your"
say "OAuth client (the one whose client ID is in your .env), open Clients → your Web client and, under"
say "'Authorized redirect URIs', ADD (keep the localhost one for development):"
say "    $BASE_URL/auth/callback"
say "Also check Audience / OAuth consent screen: keep Testing mode and only your own email as a test user."
say "(If that page looks different: APIs & Services → Credentials → your OAuth 2.0 Web client.)"
open_url "https://console.cloud.google.com/auth/clients"
pause

declare -a VARS=(
  "GCP_PROJECT_ID=$PROJECT_ID" "GCP_REGION=$REGION" "GCP_WIF_PROVIDER=$WIF_PROVIDER"
  "GCP_DEPLOY_SA=$DEPLOY_SA" "GCP_RUNTIME_SA=$RUNTIME_SA" "GCP_BUCKET=$BUCKET" "BASE_URL=$BASE_URL"
)
say ""
say "GitHub repository variables the Deploy workflow reads (none is secret):"
for kv in "${VARS[@]}"; do say "    ${kv%%=*} = ${kv#*=}"; done
if [[ $HAVE_GH = 1 ]]; then
  confirm "Set these as variables on $GITHUB_REPO using the GitHub CLI?"
  for kv in "${VARS[@]}"; do run gh variable set "${kv%%=*}" --body "${kv#*=}" --repo "$GITHUB_REPO"; done
else
  say ""
  say "Add them by hand: Settings → Secrets and variables → Actions → Variables tab → New repository variable."
  open_url "https://github.com/$GITHUB_REPO/settings/variables/actions"
  pause
fi

# ---------------------------------------------------------------- done
say ""
say "Done. Google Cloud is ready. Next (see docs/deploy.md, 'After the setup script'):"
say "  1. Merge your feature branch into main yourself (the Deploy workflow runs from main)."
say "  2. GitHub → Actions → Deploy → Run workflow → branch: main."
say "  3. Open $BASE_URL and sign in. If the real URL printed by the workflow differs, update BASE_URL and the Google"
say "     redirect URI to match, and run Deploy again."

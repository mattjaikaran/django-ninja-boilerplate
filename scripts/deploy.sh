#!/usr/bin/env bash
# Django Ninja Boilerplate — Multi-Provider Deploy Script
#
# Deploys the application to any supported cloud provider.
#
# Usage:
#   ./scripts/deploy.sh                          # deploy using DEPLOY_PROVIDER from .env.deploy
#   ./scripts/deploy.sh --provider railway       # deploy to Railway
#   ./scripts/deploy.sh --provider vps --quick   # quick restart on VPS
#   ./scripts/deploy.sh --dry-run                # show what would happen
#   ./scripts/deploy.sh --provider fly --safe    # run tests before deploying
#
# Supported providers: railway, render, fly, aws, gcp, vps
#
# Prerequisites:
#   - Provider CLI installed and authenticated (run: just deploy-setup)
#   - .env.deploy configured (copy from .env.deploy.example)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[deploy]${NC} $*"; }
ok()    { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
fail()  { echo -e "${RED}[deploy]${NC} $*"; exit 1; }
step()  { CURRENT_STEP="${*%...}"; echo -e "${BOLD}${CYAN}[deploy]${NC} ${BOLD}$*${NC}"; }
mark_step() { CURRENT_STEP="${*%...}"; info "$*"; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROVIDER=""
QUICK=false
DRY_RUN=false
SAFE=false
YES=false
BRANCH=""

# Deploy notification state (see the Deploy notifications section)
DEPLOY_STARTED=false
DEPLOY_NOTIFIED=false
DEPLOY_START_EPOCH=0
CURRENT_STEP="preflight"
HEALTH_STATUS=""
NOTIFY_CHANNELS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --provider|-p)
            PROVIDER="$2"
            shift 2
            ;;
        --quick|-q)
            QUICK=true
            shift
            ;;
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --safe|-s)
            SAFE=true
            shift
            ;;
        --yes|-y)
            YES=true
            shift
            ;;
        --branch|-b)
            BRANCH="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --provider, -p  Provider (railway|render|fly|aws|gcp|vps)"
            echo "  --quick, -q     Quick deploy (VPS: pull, incremental build, migrate, restart; no rollback marker or health check)"
            echo "  --dry-run, -n   Show what would happen without executing"
            echo "  --safe, -s      Run lint + tests before deploying"
            echo "  --yes, -y       Skip confirmation prompt"
            echo "  --branch, -b    Branch to deploy (VPS mode, default: main)"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
        *)
            if [[ -z "${BRANCH}" ]]; then
                BRANCH="$1"
            fi
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Load configuration
# ---------------------------------------------------------------------------
ENV_DEPLOY="${PROJECT_ROOT}/.env.deploy"

if [[ -f "${ENV_DEPLOY}" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${ENV_DEPLOY}"
    set +a
fi

PROVIDER="${PROVIDER:-${DEPLOY_PROVIDER:-}}"
APP_NAME="${APP_NAME:-$(basename "${PROJECT_ROOT}")}"
BRANCH="${BRANCH:-${DEPLOY_BRANCH:-main}}"

if [[ -z "${PROVIDER}" ]]; then
    fail "No provider specified. Set DEPLOY_PROVIDER in .env.deploy or use --provider flag.
  Supported: railway, render, fly, aws, gcp, vps
  Run 'just deploy-setup' to configure."
fi

# Normalize provider name
PROVIDER=$(echo "${PROVIDER}" | tr '[:upper:]' '[:lower:]')
case "${PROVIDER}" in
    railway|render|fly|fly.io|flyio|aws|gcp|vps|hetzner|self-hosted|selfhosted)
        # Normalize aliases
        case "${PROVIDER}" in
            fly.io|flyio) PROVIDER="fly" ;;
            hetzner|self-hosted|selfhosted) PROVIDER="vps" ;;
        esac
        ;;
    *)
        fail "Unknown provider: ${PROVIDER}. Supported: railway, render, fly, aws, gcp, vps"
        ;;
esac

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        if [[ "${DRY_RUN}" == true ]]; then
            warn "'$1' is not installed (would fail in real deploy)."
        else
            fail "'$1' is not installed. Run 'just deploy-setup' to install provider CLIs."
        fi
    fi
}

dry_run_cmd() {
    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] $*"
    else
        "$@"
    fi
}

confirm_deploy() {
    if [[ "${DRY_RUN}" == true ]] || [[ "${YES}" == true ]]; then
        return
    fi
    echo ""
    info "Provider:  ${BOLD}${PROVIDER}${NC}"
    info "App:       ${BOLD}${APP_NAME}${NC}"
    [[ "${PROVIDER}" == "vps" ]] && info "Host:      ${BOLD}${DEPLOY_HOST:-unset}${NC}"
    [[ "${PROVIDER}" == "vps" ]] && info "Branch:    ${BOLD}${BRANCH}${NC}"
    echo ""
    # A Ctrl-C at the prompt is not a failed deploy: notify only after "y".
    DEPLOY_STARTED=false
    read -rp "$(echo -e "${YELLOW}[deploy]${NC} Proceed with deploy? [y/N] ")" confirm
    if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
        info "Deploy cancelled."
        exit 0
    fi
    DEPLOY_STARTED=true
}

# ---------------------------------------------------------------------------
# Pre-deploy hooks
# ---------------------------------------------------------------------------
pre_deploy() {
    # Production settings default ALLOWED_HOSTS to [] so Django rejects every
    # request (400 DisallowedHost). Catch the omission before it reaches prod.
    if [[ -z "${ALLOWED_HOSTS:-}" ]]; then
        warn "ALLOWED_HOSTS is not set. Production will reject all requests with 400."
        warn "Set ALLOWED_HOSTS in .env.deploy (and in the target's .env) before deploying."
    fi
    if [[ -z "${CORS_ALLOWED_ORIGINS:-}" || -z "${CSRF_TRUSTED_ORIGINS:-}" ]]; then
        warn "CORS_ALLOWED_ORIGINS / CSRF_TRUSTED_ORIGINS are not set. Cross-origin browser calls and admin logins may fail."
    fi

    if [[ "${SAFE}" == true ]]; then
        step "Running pre-deploy checks (--safe)..."
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] would run: ruff check ."
            info "[dry-run] would run: pytest"
        else
            cd "${PROJECT_ROOT}"
            info "Linting..."
            uv run ruff check . || fail "Lint failed. Fix issues before deploying."
            info "Running tests..."
            uv run pytest --tb=short -q || fail "Tests failed. Fix issues before deploying."
            ok "Pre-deploy checks passed."
        fi
    fi
}

# ---------------------------------------------------------------------------
# Provider: Railway
# ---------------------------------------------------------------------------
deploy_railway() {
    step "Deploying to Railway..."
    require_cmd railway

    local service_flag=""
    if [[ -n "${RAILWAY_SERVICE_ID:-}" ]]; then
        service_flag="--service ${RAILWAY_SERVICE_ID}"
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] railway up ${service_flag}"
        info "[dry-run] Using Dockerfile: deploy/docker/Dockerfile.single"
        return
    fi

    cd "${PROJECT_ROOT}"

    # Link project if not already linked
    if [[ -n "${RAILWAY_PROJECT_ID:-}" ]]; then
        railway link "${RAILWAY_PROJECT_ID}" 2>/dev/null || true
    fi

    # Deploy
    # shellcheck disable=SC2086
    railway up ${service_flag}

    ok "Railway deploy triggered."
    info "Check status: railway status"
    info "View logs: railway logs"
}

# ---------------------------------------------------------------------------
# Provider: Render
# ---------------------------------------------------------------------------
deploy_render() {
    step "Deploying to Render..."

    if [[ -n "${RENDER_API_KEY:-}" && -n "${RENDER_SERVICE_ID:-}" ]]; then
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] Triggering Render deploy via API for service ${RENDER_SERVICE_ID}"
            return
        fi

        # Trigger deploy via Render API
        local response
        response=$(curl -s -w "\n%{http_code}" -X POST \
            "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
            -H "Authorization: Bearer ${RENDER_API_KEY}" \
            -H "Content-Type: application/json")

        local http_code
        http_code=$(echo "${response}" | tail -1)
        if [[ "${http_code}" == "201" ]]; then
            ok "Render deploy triggered successfully."
        else
            fail "Render API returned HTTP ${http_code}. Check your RENDER_API_KEY and RENDER_SERVICE_ID."
        fi
    elif command -v render &>/dev/null; then
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] render deploy"
            return
        fi
        cd "${PROJECT_ROOT}"
        render deploy
        ok "Render deploy triggered."
    else
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] Would deploy via Render API or CLI (neither configured)"
            return
        fi
        fail "No Render CLI or API key configured. Set RENDER_API_KEY + RENDER_SERVICE_ID, or install render CLI."
    fi

    info "Check status: https://dashboard.render.com"
}

# ---------------------------------------------------------------------------
# Provider: Fly.io
# ---------------------------------------------------------------------------
deploy_fly() {
    step "Deploying to Fly.io..."
    require_cmd fly

    local app_flag=""
    if [[ -n "${FLY_APP:-}" ]]; then
        app_flag="--app ${FLY_APP}"
    fi

    local region_flag=""
    if [[ -n "${FLY_REGION:-}" ]]; then
        region_flag="--region ${FLY_REGION}"
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] fly deploy ${app_flag} ${region_flag}"
        return
    fi

    cd "${PROJECT_ROOT}"

    # Run migrations before deploy if fly.toml exists
    if [[ -f "fly.toml" ]] || [[ -n "${FLY_APP:-}" ]]; then
        info "Running migrations..."
        # shellcheck disable=SC2086
        fly ssh console ${app_flag} -C "python manage.py migrate --noinput" 2>/dev/null || true
    fi

    # Deploy
    # shellcheck disable=SC2086
    fly deploy ${app_flag} ${region_flag}

    ok "Fly.io deploy complete."
    # shellcheck disable=SC2086
    info "Check status: fly status ${app_flag}"
}

# ---------------------------------------------------------------------------
# Provider: AWS (ECS / Copilot)
# ---------------------------------------------------------------------------
deploy_aws() {
    step "Deploying to AWS..."

    local aws_region="${AWS_REGION:-us-east-1}"

    # Prefer Copilot if available and configured
    if command -v copilot &>/dev/null && [[ -d "${PROJECT_ROOT}/copilot" ]]; then
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] copilot svc deploy --name api --env production"
            return
        fi

        cd "${PROJECT_ROOT}"
        copilot svc deploy --name "${AWS_COPILOT_SVC:-api}" --env "${AWS_COPILOT_ENV:-production}"
        ok "AWS Copilot deploy complete."
        return
    fi

    require_cmd aws

    local cluster="${AWS_CLUSTER:-}"
    local service="${AWS_SERVICE:-}"
    local ecr_repo="${AWS_ECR_REPO:-}"

    if [[ "${DRY_RUN}" == true ]]; then
        if [[ -n "${ecr_repo}" ]]; then
            info "[dry-run] docker build + push to ${ecr_repo}"
        fi
        info "[dry-run] aws ecs update-service --cluster ${cluster:-\$AWS_CLUSTER} --service ${service:-\$AWS_SERVICE} --force-new-deployment --region ${aws_region}"
        return
    fi

    if [[ -z "${cluster}" || -z "${service}" ]]; then
        fail "AWS_CLUSTER and AWS_SERVICE must be set in .env.deploy"
    fi

    # Build and push to ECR if configured
    if [[ -n "${ecr_repo}" ]]; then
        info "Building and pushing Docker image to ECR..."
        aws ecr get-login-password --region "${aws_region}" | docker login --username AWS --password-stdin "${ecr_repo%%/*}"

        local image_tag
        image_tag="${ecr_repo}:$(git rev-parse --short HEAD)"
        docker build -f deploy/docker/Dockerfile.single -t "${image_tag}" .
        docker push "${image_tag}"
        ok "Image pushed: ${image_tag}"
    fi

    # Force new deployment
    info "Updating ECS service..."
    aws ecs update-service \
        --cluster "${cluster}" \
        --service "${service}" \
        --force-new-deployment \
        --region "${aws_region}" \
        --output text --query 'service.serviceName'

    ok "AWS ECS deploy triggered."
    info "Check status: aws ecs describe-services --cluster ${cluster} --services ${service} --region ${aws_region}"
}

# ---------------------------------------------------------------------------
# Provider: GCP (Cloud Run)
# ---------------------------------------------------------------------------
deploy_gcp() {
    step "Deploying to GCP Cloud Run..."
    require_cmd gcloud

    local project="${GCP_PROJECT:-}"
    local region="${GCP_REGION:-us-central1}"
    local service="${GCP_SERVICE:-${APP_NAME}}"

    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] gcloud run deploy ${service} --source . --project ${project:-\$GCP_PROJECT} --region ${region}"
        return
    fi

    if [[ -z "${project}" ]]; then
        fail "GCP_PROJECT must be set in .env.deploy"
    fi

    cd "${PROJECT_ROOT}"

    # Deploy from source (Cloud Build) or pre-built image
    if [[ -n "${GCP_IMAGE:-}" ]]; then
        info "Deploying pre-built image: ${GCP_IMAGE}"
        gcloud run deploy "${service}" \
            --image "${GCP_IMAGE}" \
            --project "${project}" \
            --region "${region}" \
            --platform managed \
            --allow-unauthenticated
    else
        info "Building and deploying from source..."
        gcloud run deploy "${service}" \
            --source . \
            --project "${project}" \
            --region "${region}" \
            --platform managed \
            --allow-unauthenticated \
            --dockerfile deploy/docker/Dockerfile.single
    fi

    ok "GCP Cloud Run deploy complete."
    info "URL: $(gcloud run services describe "${service}" --project "${project}" --region "${region}" --format 'value(status.url)' 2>/dev/null || echo 'check console')"
}

# ---------------------------------------------------------------------------
# Provider: VPS (SSH-based — Hetzner, DigitalOcean, self-hosted)
# ---------------------------------------------------------------------------
deploy_vps() {
    local host="${DEPLOY_HOST:-}"
    local user="${DEPLOY_USER:-root}"
    local port="${DEPLOY_PORT:-22}"
    local app_dir="${DEPLOY_APP_DIR:-/opt/app}"
    local compose_file="${COMPOSE_FILE:-docker-compose.yml}"
    local profiles="${DEPLOY_PROFILES:-prod}"

    local ssh_cmd="ssh -o StrictHostKeyChecking=accept-new -p ${port} ${user}@${host}"

    step "Deploying to VPS: ${user}@${host:-\$DEPLOY_HOST}:${app_dir}"

    # Build profile flags first so the dry run prints the real command.
    local profile_flags=""
    if [[ -n "${profiles}" ]]; then
        IFS=',' read -ra PROFS <<< "${profiles}"
        for p in "${PROFS[@]}"; do
            profile_flags="${profile_flags} --profile ${p}"
        done
    fi

    local dc="docker compose -f ${compose_file} ${profile_flags}"

    if [[ "${DRY_RUN}" == true ]]; then
        local mode="full"
        [[ "${QUICK}" == true ]] && mode="quick"
        info "[dry-run] ${mode} deploy over SSH to ${user}@${host}:${port}"
        info "[dry-run] cd ${app_dir} && git pull --rebase origin ${BRANCH}"
        info "[dry-run] ${dc} build"
        info "[dry-run] ${dc} up -d --wait db-prod valkey-prod"
        info "[dry-run] ${dc} run --rm --no-deps django-prod python manage.py migrate --noinput"
        info "[dry-run] ${dc} up -d --remove-orphans"
        return
    fi

    if [[ -z "${host}" ]]; then
        fail "DEPLOY_HOST must be set for VPS deploys. Configure in .env.deploy"
    fi

    # Verify SSH connectivity
    ${ssh_cmd} "echo 'SSH OK'" 2>/dev/null || fail "Cannot SSH into ${host}"

    # Quick mode: the same build, migrate, and restart steps as a full deploy,
    # without the rollback marker and health check. Production images copy the
    # source at build time, so a restart without a build would ship old code.
    # Migrate with the new image before its containers replace the old ones.
    if [[ "${QUICK}" == true ]]; then
        mark_step "Quick deploy: pull, incremental build, migrate, restart..."
        ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
git pull --rebase origin ${BRANCH}
${dc} build
${dc} up -d --wait db-prod valkey-prod
${dc} run --rm --no-deps django-prod python manage.py migrate --noinput
${dc} up -d --remove-orphans
echo "Quick deploy complete."
REMOTE
        ok "Quick deploy finished."
        return
    fi

    # Full deploy
    mark_step "Step 1/5: Creating rollback marker..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
CURRENT_COMMIT=\$(git rev-parse HEAD 2>/dev/null || echo "none")
echo "\${CURRENT_COMMIT}" > /tmp/${APP_NAME}-pre-deploy-commit
echo "Pre-deploy commit: \${CURRENT_COMMIT}"
REMOTE

    mark_step "Step 2/5: Pulling latest code..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
git fetch origin
git checkout ${BRANCH}
git pull --rebase origin ${BRANCH}
echo "Now at: \$(git rev-parse --short HEAD) — \$(git log -1 --format='%s')"
REMOTE

    mark_step "Step 3/5: Building Docker images..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 ${dc} build
REMOTE

    mark_step "Step 4/5: Running migrations and starting services..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
${dc} up -d --wait db-prod valkey-prod
${dc} run --rm --no-deps django-prod python manage.py migrate --noinput
${dc} up -d --remove-orphans
REMOTE

    mark_step "Step 5/5: Health check..."
    sleep 8
    local health_rc=0
    ${ssh_cmd} << REMOTE || health_rc=$?
set -euo pipefail
cd ${app_dir}

echo "--- Container Status ---"
${dc} ps

echo ""
echo "--- Health Check ---"
health_ok=false
for i in \$(seq 1 12); do
    # nginx is the only prod service with a host port; django-prod is expose-only.
    if curl -sf http://localhost/api/health/ > /dev/null 2>&1; then
        echo "API Health: OK"
        health_ok=true
        break
    fi
    if [ \$i -eq 12 ]; then
        echo "WARNING: Health check did not pass within 60s"
        echo "Check logs: docker compose -f ${compose_file} --profile prod logs django-prod"
    fi
    sleep 5
done

echo ""
echo "Deployed: \$(git rev-parse --short HEAD) — \$(git log -1 --format='%s')"
# Exit 3 tells the local script that the health check did not pass.
if [ "\$health_ok" != true ]; then exit 3; fi
REMOTE

    if (( health_rc == 3 )); then
        HEALTH_STATUS="failed"
        fail "Health check did not pass. The deploy is marked failed. Check the logs on ${host}."
    fi
    if (( health_rc != 0 )); then
        fail "Health check step failed over SSH (exit ${health_rc})."
    fi
    HEALTH_STATUS="ok"

    ok "VPS deploy complete."
}

# ---------------------------------------------------------------------------
# Deploy notifications
# ---------------------------------------------------------------------------
# Channels: webhook (DEPLOY_WEBHOOK_URL), telegram (TELEGRAM_BOT_TOKEN and
# TELEGRAM_CHAT_ID), hermes (HERMES_URL). DEPLOY_NOTIFY picks a comma list.
# Unset or empty means every channel whose settings are present. "none" is off.
# A failed notification warns. It never fails the deploy.

# Print one JSON object from KEY VALUE pairs. Values go in as argv, so quotes
# and backslashes in commit subjects stay inert.
json_object() {
    if command -v jq &>/dev/null; then
        jq -cn --args -- '$ARGS.positional as $a
            | reduce range(0; $a | length; 2) as $i ({}; . + {($a[$i]): $a[$i + 1]})' "$@"
    elif command -v python3 &>/dev/null; then
        python3 -c 'import json, sys; a = sys.argv[1:]; print(json.dumps(dict(zip(a[::2], a[1::2]))))' "$@"
    else
        return 1
    fi
}

channel_configured() {
    case "$1" in
        webhook)  [[ -n "${DEPLOY_WEBHOOK_URL:-}" ]] ;;
        telegram) [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]] ;;
        hermes)   [[ -n "${HERMES_URL:-}" ]] ;;
        *)        return 1 ;;
    esac
}

# Fill NOTIFY_CHANNELS from DEPLOY_NOTIFY, or from every configured channel.
resolve_notify_channels() {
    NOTIFY_CHANNELS=()
    local raw="${DEPLOY_NOTIFY:-}" item name
    raw="${raw//[[:space:]]/}"
    if [[ -z "${raw}" ]]; then
        for name in webhook telegram hermes; do
            if channel_configured "${name}"; then
                NOTIFY_CHANNELS+=("${name}")
            fi
        done
        return 0
    fi

    local -a items
    IFS=',' read -ra items <<< "${raw}"
    for item in "${items[@]}"; do
        name="$(printf '%s' "${item}" | tr '[:upper:]' '[:lower:]')"
        case "${name}" in
            ""|none) ;;
            webhook|telegram|hermes)
                if channel_configured "${name}"; then
                    NOTIFY_CHANNELS+=("${name}")
                else
                    warn "DEPLOY_NOTIFY lists ${name}, but its settings are unset. Skipped."
                fi
                ;;
            *)
                warn "Unknown DEPLOY_NOTIFY channel: ${name}. Use webhook, telegram, or hermes."
                ;;
        esac
    done
    return 0
}

# Send one payload to one channel. Returns non-zero when delivery fails.
deliver() {
    local channel="$1" envelope="$2" text="$3" payload
    case "${channel}" in
        webhook)
            curl -fsS --max-time 15 -X POST "${DEPLOY_WEBHOOK_URL}" \
                -H "Content-Type: application/json" --data "${envelope}" >/dev/null 2>&1
            ;;
        hermes)
            curl -fsS --max-time 15 -X POST "${HERMES_URL%/}/deploy_webhook" \
                -H "Content-Type: application/json" --data "${envelope}" >/dev/null 2>&1
            ;;
        telegram)
            # The token goes to curl as a config on stdin, never argv, so ps
            # cannot show it. printf is a builtin. Silence curl for the log too.
            payload="$(json_object chat_id "${TELEGRAM_CHAT_ID}" text "${text}")" || return 1
            printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "${TELEGRAM_BOT_TOKEN}" \
                | curl -fsS --max-time 15 -X POST -K - \
                    -H "Content-Type: application/json" --data "${payload}" >/dev/null 2>&1
            ;;
    esac
}

# notify_deploy EVENT EXIT_CODE. EVENT is deploy_complete or deploy_failed.
notify_deploy() {
    local event="$1" exit_code="$2"
    DEPLOY_NOTIFIED=true

    resolve_notify_channels
    if [[ -z "${NOTIFY_CHANNELS[*]-}" ]]; then
        if [[ "${DRY_RUN}" == true ]]; then
            info "[dry-run] ${event}: no notification channel configured."
        fi
        return 0
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] ${event} would notify: ${NOTIFY_CHANNELS[*]}"
        return 0
    fi

    local commit commit_short subject duration failed_step="" envelope text
    commit="$(git -C "${PROJECT_ROOT}" rev-parse HEAD 2>/dev/null || echo "unknown")"
    commit_short="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
    subject="$(git -C "${PROJECT_ROOT}" log -1 --format=%s 2>/dev/null || true)"
    duration=$(( $(date +%s) - DEPLOY_START_EPOCH ))
    if [[ "${event}" == deploy_failed ]]; then
        failed_step="${CURRENT_STEP}"
    fi

    envelope="$(json_object \
        event "${event}" \
        app "${APP_NAME}" \
        commit "${commit}" \
        commit_short "${commit_short}" \
        subject "${subject}" \
        env "${DEPLOY_ENV:-production}" \
        frontend_url "${FRONTEND_URL:-}" \
        backend_url "${BACKEND_URL:-}" \
        provider "${PROVIDER}" \
        duration_seconds "${duration}" \
        health "${HEALTH_STATUS}" \
        failed_step "${failed_step}" \
        exit_code "${exit_code}")" || {
        warn "Deploy notification skipped: install jq or python3 to build the payload."
        return 0
    }

    # The first lines match mattstack-cli _format_message. The rest are extra fields.
    local -a lines
    lines=("${event}: ${APP_NAME}" "commit: ${commit_short}" "env: ${DEPLOY_ENV:-production}")
    if [[ -n "${FRONTEND_URL:-}" ]]; then
        lines+=("frontend: ${FRONTEND_URL}")
    fi
    if [[ -n "${BACKEND_URL:-}" ]]; then
        lines+=("backend: ${BACKEND_URL}")
    fi
    lines+=("provider: ${PROVIDER}" "subject: ${subject}" "duration: ${duration}s")
    if [[ -n "${HEALTH_STATUS}" ]]; then
        lines+=("health: ${HEALTH_STATUS}")
    fi
    if [[ "${event}" == deploy_failed ]]; then
        lines+=("step: ${failed_step}" "exit code: ${exit_code}")
    fi
    text="$(printf '%s\n' "${lines[@]}")"

    local channel
    for channel in "${NOTIFY_CHANNELS[@]}"; do
        if deliver "${channel}" "${envelope}" "${text}"; then
            ok "Deploy notification sent to ${channel}."
        else
            warn "Deploy notification to ${channel} failed. The deploy result is unchanged."
        fi
    done
    return 0
}

# EXIT trap: report a failed provider deploy, whatever stopped it.
on_exit() {
    local rc=$?
    trap - EXIT
    if [[ "${DEPLOY_STARTED}" == true && "${DEPLOY_NOTIFIED}" != true ]]; then
        local event="deploy_failed"
        if (( rc == 0 )); then
            event="deploy_complete"
        fi
        notify_deploy "${event}" "${rc}" || true
    fi
    exit "${rc}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
info "Provider: ${PROVIDER} | App: ${APP_NAME}"
echo ""

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Pre-deploy failures (for example --safe checks) also send deploy_failed.
# confirm_deploy resets DEPLOY_STARTED on cancel, so a cancel sends nothing.
DEPLOY_STARTED=true
DEPLOY_START_EPOCH="$(date +%s)"
pre_deploy
confirm_deploy

case "${PROVIDER}" in
    railway) deploy_railway ;;
    render)  deploy_render ;;
    fly)     deploy_fly ;;
    aws)     deploy_aws ;;
    gcp)     deploy_gcp ;;
    vps)     deploy_vps ;;
esac
notify_deploy deploy_complete 0 || true

echo ""
ok "Done."

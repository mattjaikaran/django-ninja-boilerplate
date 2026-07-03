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
#   - Provider CLI installed and authenticated (run: make deploy-setup)
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
step()  { echo -e "${BOLD}${CYAN}[deploy]${NC} ${BOLD}$*${NC}"; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROVIDER=""
QUICK=false
DRY_RUN=false
SAFE=false
YES=false
BRANCH=""

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
            echo "  --quick, -q     Quick deploy (VPS: skip rebuild, just restart)"
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
  Run 'make deploy-setup' to configure."
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
            fail "'$1' is not installed. Run 'make deploy-setup' to install provider CLIs."
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
    read -rp "$(echo -e "${YELLOW}[deploy]${NC} Proceed with deploy? [y/N] ")" confirm
    if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
        info "Deploy cancelled."
        exit 0
    fi
}

# ---------------------------------------------------------------------------
# Pre-deploy hooks
# ---------------------------------------------------------------------------
pre_deploy() {
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
    local compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
    local profiles="${DEPLOY_PROFILES:-}"

    local ssh_cmd="ssh -o StrictHostKeyChecking=accept-new -p ${port} ${user}@${host}"

    step "Deploying to VPS: ${user}@${host:-\$DEPLOY_HOST}:${app_dir}"

    if [[ "${DRY_RUN}" == true ]]; then
        info "[dry-run] SSH to ${user}@${host}:${port}"
        info "[dry-run] cd ${app_dir} && git pull --rebase origin ${BRANCH}"
        info "[dry-run] docker compose -f ${compose_file} build && up -d"
        info "[dry-run] python manage.py migrate --noinput"
        return
    fi

    if [[ -z "${host}" ]]; then
        fail "DEPLOY_HOST must be set for VPS deploys. Configure in .env.deploy"
    fi

    # Verify SSH connectivity
    ${ssh_cmd} "echo 'SSH OK'" 2>/dev/null || fail "Cannot SSH into ${host}"

    # Build profile flags
    local profile_flags=""
    if [[ -n "${profiles}" ]]; then
        IFS=',' read -ra PROFS <<< "${profiles}"
        for p in "${PROFS[@]}"; do
            profile_flags="${profile_flags} --profile ${p}"
        done
    fi

    local dc="docker compose -f ${compose_file} ${profile_flags}"

    # Quick mode
    if [[ "${QUICK}" == true ]]; then
        info "Quick deploy — pulling code and restarting..."
        ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
git pull --rebase origin ${BRANCH}
${dc} up -d --remove-orphans
${dc} exec -T django python manage.py migrate --noinput 2>/dev/null || true
echo "Quick deploy complete."
REMOTE
        ok "Quick deploy finished."
        return
    fi

    # Full deploy
    info "Step 1/5: Creating rollback marker..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
CURRENT_COMMIT=\$(git rev-parse HEAD 2>/dev/null || echo "none")
echo "\${CURRENT_COMMIT}" > /tmp/${APP_NAME}-pre-deploy-commit
echo "Pre-deploy commit: \${CURRENT_COMMIT}"
REMOTE

    info "Step 2/5: Pulling latest code..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
git fetch origin
git checkout ${BRANCH}
git pull --rebase origin ${BRANCH}
echo "Now at: \$(git rev-parse --short HEAD) — \$(git log -1 --format='%s')"
REMOTE

    info "Step 3/5: Building Docker images..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 ${dc} build
REMOTE

    info "Step 4/5: Running migrations and starting services..."
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}
${dc} up -d db redis 2>/dev/null || ${dc} up -d postgres redis 2>/dev/null || true
sleep 5
${dc} run --rm --no-deps django python manage.py migrate --noinput 2>/dev/null || \
    ${dc} run --rm django python manage.py migrate --noinput
${dc} up -d --remove-orphans
REMOTE

    info "Step 5/5: Health check..."
    sleep 8
    ${ssh_cmd} << REMOTE
set -euo pipefail
cd ${app_dir}

echo "--- Container Status ---"
${dc} ps

echo ""
echo "--- Health Check ---"
for i in \$(seq 1 12); do
    if curl -sf http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "API Health: OK"
        break
    fi
    if [ \$i -eq 12 ]; then
        echo "WARNING: Health check did not pass within 60s"
        echo "Check logs: docker compose -f ${compose_file} logs django"
    fi
    sleep 5
done

echo ""
echo "Deployed: \$(git rev-parse --short HEAD) — \$(git log -1 --format='%s')"
REMOTE

    ok "VPS deploy complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
info "Provider: ${PROVIDER} | App: ${APP_NAME}"
echo ""

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

echo ""
ok "Done."

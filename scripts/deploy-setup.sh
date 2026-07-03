#!/usr/bin/env bash
# Django Ninja Boilerplate — Deploy Setup
#
# One-time setup for deployment provider CLIs and configuration.
# Installs CLIs, guides through authentication, and creates .env.deploy.
#
# Usage:
#   ./scripts/deploy-setup.sh              # interactive setup
#   ./scripts/deploy-setup.sh railway      # setup Railway only
#   ./scripts/deploy-setup.sh --install    # install all CLIs without auth

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[setup]${NC} $*"; }
ok()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $*"; }
fail()  { echo -e "${RED}[setup]${NC} $*"; exit 1; }
step()  { echo -e "${BOLD}${CYAN}[setup]${NC} ${BOLD}$*${NC}"; }

# ---------------------------------------------------------------------------
# Detect OS and package manager
# ---------------------------------------------------------------------------
OS="$(uname -s)"

install_with_brew() {
    if command -v brew &>/dev/null; then
        brew install "$1"
    else
        fail "Homebrew not found. Install manually: $2"
    fi
}

install_with_curl() {
    info "Installing via: $1"
    eval "$1"
}

# ---------------------------------------------------------------------------
# CLI installers
# ---------------------------------------------------------------------------
install_railway() {
    if command -v railway &>/dev/null; then
        ok "Railway CLI already installed: $(railway --version 2>/dev/null || echo 'installed')"
        return
    fi

    info "Installing Railway CLI..."
    case "${OS}" in
        Darwin)
            install_with_brew "railway" "https://docs.railway.app/guides/cli"
            ;;
        Linux)
            install_with_curl "curl -fsSL https://railway.app/install.sh | sh"
            ;;
        *)
            fail "Unsupported OS for Railway CLI. Install manually: https://docs.railway.app/guides/cli"
            ;;
    esac
    ok "Railway CLI installed."
}

install_fly() {
    if command -v fly &>/dev/null || command -v flyctl &>/dev/null; then
        ok "Fly CLI already installed: $(fly version 2>/dev/null || flyctl version 2>/dev/null)"
        return
    fi

    info "Installing Fly.io CLI..."
    case "${OS}" in
        Darwin)
            install_with_brew "flyctl" "https://fly.io/docs/flyctl/install/"
            ;;
        Linux)
            install_with_curl "curl -L https://fly.io/install.sh | sh"
            ;;
        *)
            fail "Unsupported OS for Fly CLI. Install manually: https://fly.io/docs/flyctl/install/"
            ;;
    esac
    ok "Fly CLI installed."
}

install_render() {
    if command -v render &>/dev/null; then
        ok "Render CLI already installed."
        return
    fi

    info "Installing Render CLI..."
    case "${OS}" in
        Darwin)
            install_with_brew "render" "https://render.com/docs/cli"
            ;;
        Linux)
            warn "Render CLI: Install from https://render.com/docs/cli"
            warn "Alternatively, set RENDER_API_KEY in .env.deploy for API-based deploys."
            ;;
        *)
            warn "Install Render CLI manually: https://render.com/docs/cli"
            ;;
    esac
}

install_aws() {
    if command -v aws &>/dev/null; then
        ok "AWS CLI already installed: $(aws --version 2>/dev/null | head -1)"
    else
        info "Installing AWS CLI..."
        case "${OS}" in
            Darwin)
                install_with_brew "awscli" "https://aws.amazon.com/cli/"
                ;;
            Linux)
                install_with_curl 'curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip" && unzip -qo /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install'
                ;;
            *)
                fail "Install AWS CLI manually: https://aws.amazon.com/cli/"
                ;;
        esac
        ok "AWS CLI installed."
    fi

    # Copilot (optional)
    if ! command -v copilot &>/dev/null; then
        info "Installing AWS Copilot CLI (optional, for ECS)..."
        case "${OS}" in
            Darwin)
                install_with_brew "aws/tap/copilot-cli" "https://aws.github.io/copilot-cli/"
                ;;
            Linux)
                install_with_curl 'curl -Lo /usr/local/bin/copilot https://github.com/aws/copilot-cli/releases/latest/download/copilot-linux && chmod +x /usr/local/bin/copilot'
                ;;
            *)
                warn "Install Copilot CLI manually: https://aws.github.io/copilot-cli/"
                ;;
        esac
    else
        ok "AWS Copilot CLI already installed."
    fi
}

install_gcp() {
    if command -v gcloud &>/dev/null; then
        ok "Google Cloud CLI already installed: $(gcloud --version 2>/dev/null | head -1)"
        return
    fi

    info "Installing Google Cloud CLI..."
    case "${OS}" in
        Darwin)
            install_with_brew "google-cloud-sdk" "https://cloud.google.com/sdk/docs/install"
            ;;
        Linux)
            install_with_curl 'curl -fsSL https://sdk.cloud.google.com | bash'
            ;;
        *)
            fail "Install gcloud manually: https://cloud.google.com/sdk/docs/install"
            ;;
    esac
    ok "Google Cloud CLI installed."
}

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
auth_railway() {
    info "Authenticating Railway..."
    railway login
    ok "Railway authenticated."

    echo ""
    info "To link a project, run: railway link"
    info "Or set RAILWAY_PROJECT_ID in .env.deploy"
}

auth_fly() {
    info "Authenticating Fly.io..."
    fly auth login
    ok "Fly.io authenticated."
}

auth_render() {
    if [[ -n "${RENDER_API_KEY:-}" ]]; then
        ok "Render API key already configured."
        return
    fi
    if command -v render &>/dev/null; then
        info "Authenticating Render..."
        render login
        ok "Render authenticated."
    else
        warn "Set RENDER_API_KEY in .env.deploy for API-based deploys."
    fi
}

auth_aws() {
    info "Configuring AWS credentials..."
    if aws sts get-caller-identity &>/dev/null 2>&1; then
        ok "AWS already authenticated: $(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null)"
    else
        aws configure
        ok "AWS configured."
    fi
}

auth_gcp() {
    info "Authenticating Google Cloud..."
    if gcloud auth print-identity-token &>/dev/null 2>&1; then
        ok "GCP already authenticated: $(gcloud config get-value project 2>/dev/null)"
    else
        gcloud auth login
        gcloud auth configure-docker
        ok "GCP authenticated."
    fi
}

# ---------------------------------------------------------------------------
# .env.deploy generator
# ---------------------------------------------------------------------------
create_env_deploy() {
    local provider="$1"
    local env_file="${PROJECT_ROOT}/.env.deploy"

    if [[ -f "${env_file}" ]]; then
        warn ".env.deploy already exists. Skipping creation."
        info "Edit manually: ${env_file}"
        return
    fi

    info "Creating .env.deploy for provider: ${provider}..."
    cp "${PROJECT_ROOT}/.env.deploy.example" "${env_file}" 2>/dev/null || true

    if [[ -f "${env_file}" ]]; then
        # Set the provider
        if [[ "${OS}" == "Darwin" ]]; then
            sed -i '' "s/^DEPLOY_PROVIDER=.*/DEPLOY_PROVIDER=${provider}/" "${env_file}"
        else
            sed -i "s/^DEPLOY_PROVIDER=.*/DEPLOY_PROVIDER=${provider}/" "${env_file}"
        fi
        ok "Created .env.deploy with provider=${provider}"
        info "Edit ${env_file} to fill in your configuration."
    else
        warn "Could not create .env.deploy. Copy from .env.deploy.example manually."
    fi
}

# ---------------------------------------------------------------------------
# Interactive provider selection
# ---------------------------------------------------------------------------
select_provider() {
    echo ""
    echo -e "${BOLD}Select deployment provider:${NC}"
    echo ""
    echo "  1) Railway     — PaaS, easiest setup, auto-scaling"
    echo "  2) Fly.io      — Edge compute, global deployment"
    echo "  3) Render      — PaaS, free tier, auto-deploy from Git"
    echo "  4) AWS         — ECS/Copilot, enterprise-grade"
    echo "  5) GCP         — Cloud Run, serverless containers"
    echo "  6) VPS         — Self-hosted (Hetzner, DigitalOcean, etc.)"
    echo ""
    read -rp "$(echo -e "${CYAN}[setup]${NC} Choose [1-6]: ")" choice

    case "${choice}" in
        1) echo "railway" ;;
        2) echo "fly" ;;
        3) echo "render" ;;
        4) echo "aws" ;;
        5) echo "gcp" ;;
        6) echo "vps" ;;
        *) fail "Invalid choice." ;;
    esac
}

# ---------------------------------------------------------------------------
# Full setup for a provider
# ---------------------------------------------------------------------------
setup_provider() {
    local provider="$1"

    echo ""
    step "Setting up: ${provider}"
    echo ""

    case "${provider}" in
        railway)
            install_railway
            auth_railway
            ;;
        fly)
            install_fly
            auth_fly
            ;;
        render)
            install_render
            auth_render
            ;;
        aws)
            install_aws
            auth_aws
            ;;
        gcp)
            install_gcp
            auth_gcp
            ;;
        vps)
            info "VPS deployment uses SSH. Ensure you have:"
            echo "  - SSH key access to your server"
            echo "  - Docker + Docker Compose installed on server"
            echo "  - Git repo cloned on server"
            echo ""
            info "Configure DEPLOY_HOST, DEPLOY_USER, DEPLOY_APP_DIR in .env.deploy"
            ;;
        *)
            fail "Unknown provider: ${provider}"
            ;;
    esac

    create_env_deploy "${provider}"

    echo ""
    ok "Setup complete for ${provider}!"
    info "Next: edit .env.deploy, then run 'make deploy'"
}

# ---------------------------------------------------------------------------
# Install-only mode
# ---------------------------------------------------------------------------
install_all_clis() {
    step "Installing all provider CLIs..."
    echo ""
    install_railway
    install_fly
    install_render
    install_aws
    install_gcp
    echo ""
    ok "All CLIs installed. Run this script again with a provider name to authenticate."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Deploy Setup — Django Ninja        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

case "${1:-}" in
    --install)
        install_all_clis
        ;;
    railway|fly|render|aws|gcp|vps)
        setup_provider "$1"
        ;;
    "")
        provider=$(select_provider)
        setup_provider "${provider}"
        ;;
    *)
        echo "Usage: deploy-setup.sh [provider|--install]"
        echo ""
        echo "Providers: railway, fly, render, aws, gcp, vps"
        echo "Flags:     --install (install all CLIs without auth)"
        exit 1
        ;;
esac

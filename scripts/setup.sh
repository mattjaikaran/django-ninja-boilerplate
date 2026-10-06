#!/bin/bash

# Django Ninja Boilerplate - Development Environment Setup
# One-command project bootstrap with auto mode support
#
# Usage:
#   ./scripts/setup.sh          # Interactive mode
#   ./scripts/setup.sh --auto   # Fully automated (for CI/CD)
#   just setup                  # Runs with --auto

set -e  # Exit on any error

# ===========================================
# Configuration
# ===========================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
AUTO_MODE=false
SKIP_DOCKER=false
SKIP_SEED=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto|-a)
            AUTO_MODE=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        --help|-h)
            echo "Django Ninja Boilerplate - Setup Script"
            echo ""
            echo "Usage: ./scripts/setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --auto, -a      Run in auto mode (no prompts)"
            echo "  --skip-docker   Skip Docker build and start"
            echo "  --skip-seed     Skip seeding sample data"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ===========================================
# Print Functions
# ===========================================

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ===========================================
# Utility Functions
# ===========================================

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

wait_for_service() {
    local service=$1
    local max_attempts=${2:-30}
    local attempt=1

    while [ "$attempt" -le "$max_attempts" ]; do
        if docker compose --profile dev ps "$service" 2>/dev/null | grep -q "Up"; then
            return 0
        fi
        sleep 1
        ((attempt++))
    done
    return 1
}

wait_for_healthy() {
    local service=$1
    local max_attempts=${2:-60}
    local attempt=1

    print_info "Waiting for $service to be healthy..."
    while [ "$attempt" -le "$max_attempts" ]; do
        if docker compose --profile dev ps "$service" 2>/dev/null | grep -q "healthy"; then
            return 0
        fi
        printf "."
        sleep 2
        ((attempt++))
    done
    echo ""
    return 1
}

# ===========================================
# Validation
# ===========================================

check_requirements() {
    print_step "Checking system requirements..."

    local has_errors=false

    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is not installed"
        print_info "Install from: https://www.docker.com/get-started"
        has_errors=true
    elif ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running"
        print_info "Please start Docker Desktop or the Docker daemon"
        has_errors=true
    else
        print_success "Docker is running"
    fi

    # Check Docker Compose
    if command_exists docker-compose; then
        print_success "Docker Compose available"
    elif docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose available (plugin)"
    else
        print_error "Docker Compose not found"
        has_errors=true
    fi

    # Check UV (optional but recommended)
    if command_exists uv; then
        print_success "UV package manager available"
    else
        print_warning "UV not installed (optional for local development)"
        print_info "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi

    # Check Make (optional)
    if command_exists make; then
        print_success "Make available"
    else
        print_warning "Make not installed (optional)"
    fi

    if [ "$has_errors" = true ]; then
        print_error "Please fix the above issues and try again"
        exit 1
    fi

    print_success "All required tools are available"
}

# ===========================================
# Environment Setup
# ===========================================

setup_env_file() {
    print_step "Setting up environment file..."

    # scripts/env_secrets.py holds the one list of generated secrets. It
    # never replaces .env and never prints a secret value.
    if [ -f .env ]; then
        print_info ".env file already exists; generating only unset secrets"
        python3 scripts/env_secrets.py fill
    elif [ -f .env.development ]; then
        python3 scripts/env_secrets.py create --template .env.development
    else
        python3 scripts/env_secrets.py create
    fi
}

# ===========================================
# Docker Setup
# ===========================================

setup_docker() {
    if [ "$SKIP_DOCKER" = true ]; then
        print_info "Skipping Docker setup (--skip-docker)"
        return
    fi

    print_step "Building Docker images..."
    docker compose --profile dev build

    print_step "Starting Docker services..."
    docker compose --profile dev up -d

    # Wait for database to be healthy
    if ! wait_for_healthy "db" 60; then
        print_error "Database failed to start"
        print_info "Check logs with: docker compose --profile dev logs db"
        exit 1
    fi
    print_success "Database is healthy"

    # Wait for Valkey to be healthy
    if ! wait_for_healthy "valkey" 30; then
        print_error "Valkey failed to start"
        print_info "Check logs with: docker compose --profile dev logs valkey"
        exit 1
    fi
    print_success "Valkey is healthy"

    # Wait for Django to start
    print_info "Waiting for Django to start..."
    sleep 5

    print_success "Docker services are running"
}

# ===========================================
# Database Setup
# ===========================================

setup_database() {
    print_step "Running database migrations..."

    # Run migrations
    docker compose --profile dev exec -T django uv run python manage.py migrate --noinput
    print_success "Migrations completed"

    # Collect static files
    print_step "Collecting static files..."
    docker compose --profile dev exec -T django uv run python manage.py collectstatic --noinput
    print_success "Static files collected"
}

# ===========================================
# Seed Data
# ===========================================

seed_data() {
    if [ "$SKIP_SEED" = true ]; then
        print_info "Skipping data seeding (--skip-seed)"
        return
    fi

    print_step "Seeding sample data..."

    # Generate core data
    if docker compose --profile dev exec -T django uv run python manage.py generate_core_data 2>/dev/null; then
        print_success "Core data generated"
    else
        print_warning "generate_core_data command not available, skipping"
    fi

    # Create superuser if in auto mode
    if [ "$AUTO_MODE" = true ]; then
        print_step "Creating superuser..."
        if docker compose --profile dev exec -T django uv run python manage.py create_superuser 2>/dev/null; then
            print_success "Superuser created (check .env for credentials)"
        else
            print_warning "create_superuser command not available"
            print_info "Create manually with: just legacy createsuperuser"
        fi
    else
        # Interactive mode - ask user
        echo ""
        read -p "Would you like to create a superuser? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose --profile dev exec django uv run python manage.py createsuperuser
        fi
    fi
}

# ===========================================
# Verification
# ===========================================

verify_setup() {
    print_step "Verifying setup..."

    # Check Django health endpoint
    local max_attempts=10
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf http://localhost:8000/api/health/ >/dev/null 2>&1; then
            print_success "Django API is responding"
            return 0
        fi
        sleep 2
        ((attempt++))
    done

    print_warning "Django API not responding yet (may still be starting)"
    print_info "Check logs with: just logs-django"
}

# ===========================================
# Final Summary
# ===========================================

show_summary() {
    print_header "Setup Complete!"

    echo "Your development environment is ready."
    echo ""
    echo "Available URLs:"
    echo -e "  ${GREEN}API Documentation:${NC}  http://localhost:8000/api/docs"
    echo -e "  ${GREEN}Django Admin:${NC}       http://localhost:8000/admin"
    echo -e "  ${GREEN}Health Check:${NC}       http://localhost:8000/api/health/"
    echo ""
    echo "Useful commands:"
    echo -e "  ${CYAN}just up${NC}              Start services"
    echo -e "  ${CYAN}just down${NC}            Stop services"
    echo -e "  ${CYAN}just logs${NC}            View logs"
    echo -e "  ${CYAN}just shell${NC}           Django shell"
    echo -e "  ${CYAN}just test${NC}            Run tests"
    echo -e "  ${CYAN}just doctor${NC}          Check environment"
    echo ""
    echo "For Celery workers:"
    echo -e "  ${CYAN}just up-celery${NC}       Start with Celery"
    echo -e "  ${CYAN}just up-full${NC}         Start all services"
    echo ""

    if [ "$AUTO_MODE" = true ] && [ -f .env ]; then
        local email
        email=$(grep "^SUPERUSER_EMAIL=" .env | cut -d'=' -f2)
        echo "Superuser: ${email:-see SUPERUSER_EMAIL} (password: SUPERUSER_PASSWORD in .env)"
        echo ""
    fi

    echo -e "${GREEN}Happy coding!${NC}"
    echo ""
}

# ===========================================
# Pre-commit Hooks
# ===========================================

setup_pre_commit() {
    print_step "Setting up pre-commit hooks..."

    if command_exists uv && [ -d .git ]; then
        if [ -f .pre-commit-config.yaml ]; then
            uv run pre-commit install
            uv run pre-commit install --hook-type commit-msg
            print_success "Pre-commit hooks installed"
        else
            print_warning "No .pre-commit-config.yaml found, skipping hooks"
        fi
    else
        print_warning "uv or git not available, skipping pre-commit hooks"
        print_info "Install manually with: just legacy pre-commit-install"
    fi
}

# ===========================================
# Main Execution
# ===========================================

main() {
    print_header "Django Ninja Boilerplate - Setup"

    if [ "$AUTO_MODE" = true ]; then
        print_info "Running in auto mode (no prompts)"
    fi

    check_requirements
    setup_env_file
    setup_pre_commit
    setup_docker
    setup_database
    seed_data
    verify_setup
    show_summary
}

# Run main function
main

#!/bin/bash

# Django Ninja Boilerplate - Development Environment Setup
# One-command project bootstrap with auto mode support
#
# Usage:
#   ./scripts/setup.sh          # Interactive mode
#   ./scripts/setup.sh --auto   # Fully automated (for CI/CD)
#   make setup                  # Runs with --auto

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

generate_secret_key() {
    # Generate a Django-compatible secret key
    if command_exists python3; then
        python3 -c "import secrets; print(secrets.token_urlsafe(50))"
    elif command_exists openssl; then
        openssl rand -base64 50 | tr -d '\n/+=' | head -c 50
    else
        # Fallback to urandom
        cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1
    fi
}

wait_for_service() {
    local service=$1
    local max_attempts=${2:-30}
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
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
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps "$service" 2>/dev/null | grep -q "healthy"; then
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

    if [ -f .env ]; then
        print_info ".env file already exists"

        # Check if SECRET_KEY needs to be generated
        if grep -q "^SECRET_KEY=your-secret-key" .env 2>/dev/null || \
           grep -q "^SECRET_KEY=development-secret-key" .env 2>/dev/null || \
           grep -q "^SECRET_KEY=$" .env 2>/dev/null; then
            print_info "Generating new SECRET_KEY..."
            NEW_SECRET=$(generate_secret_key)

            # Use sed to replace the SECRET_KEY line
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" .env
            else
                sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" .env
            fi
            print_success "SECRET_KEY generated"
        fi
    else
        print_info "Creating .env file..."

        # Copy from .env.development or .env.example
        if [ -f .env.development ]; then
            cp .env.development .env
            print_info "Copied from .env.development"
        elif [ -f .env.example ]; then
            cp .env.example .env
            print_info "Copied from .env.example"
        else
            # Create minimal .env
            cat > .env << 'EOF'
# Django Ninja Boilerplate - Environment Variables
DEBUG=1
DJANGO_SETTINGS_MODULE=api.settings
SECRET_KEY=PLACEHOLDER
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,django

# Database
DB_NAME=boilerplate_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Frontend
FRONTEND_URL=http://localhost:3000
EOF
            print_info "Created minimal .env file"
        fi

        # Generate SECRET_KEY
        print_info "Generating SECRET_KEY..."
        NEW_SECRET=$(generate_secret_key)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" .env
        else
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" .env
        fi
        print_success ".env file created with generated SECRET_KEY"
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
    docker-compose build

    print_step "Starting Docker services..."
    docker-compose up -d

    # Wait for database to be healthy
    if ! wait_for_healthy "db" 60; then
        print_error "Database failed to start"
        print_info "Check logs with: docker-compose logs db"
        exit 1
    fi
    print_success "Database is healthy"

    # Wait for Redis to be healthy
    if ! wait_for_healthy "redis" 30; then
        print_error "Redis failed to start"
        print_info "Check logs with: docker-compose logs redis"
        exit 1
    fi
    print_success "Redis is healthy"

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
    docker-compose exec -T django uv run python manage.py migrate --noinput
    print_success "Migrations completed"

    # Collect static files
    print_step "Collecting static files..."
    docker-compose exec -T django uv run python manage.py collectstatic --noinput
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
    if docker-compose exec -T django uv run python manage.py generate_core_data 2>/dev/null; then
        print_success "Core data generated"
    else
        print_warning "generate_core_data command not available, skipping"
    fi

    # Create superuser if in auto mode
    if [ "$AUTO_MODE" = true ]; then
        print_step "Creating superuser..."
        if docker-compose exec -T django uv run python manage.py create_superuser 2>/dev/null; then
            print_success "Superuser created (check .env for credentials)"
        else
            print_warning "create_superuser command not available"
            print_info "Create manually with: make createsuperuser"
        fi
    else
        # Interactive mode - ask user
        echo ""
        read -p "Would you like to create a superuser? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose exec django uv run python manage.py createsuperuser
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
    print_info "Check logs with: make logs-django"
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
    echo -e "  ${CYAN}make up${NC}              Start services"
    echo -e "  ${CYAN}make down${NC}            Stop services"
    echo -e "  ${CYAN}make logs${NC}            View logs"
    echo -e "  ${CYAN}make shell${NC}           Django shell"
    echo -e "  ${CYAN}make test${NC}            Run tests"
    echo -e "  ${CYAN}make doctor${NC}          Check environment"
    echo ""
    echo "For Celery workers:"
    echo -e "  ${CYAN}make up-celery${NC}       Start with Celery"
    echo -e "  ${CYAN}make up-full${NC}         Start all services"
    echo ""

    if [ "$AUTO_MODE" = true ]; then
        echo "Superuser credentials (from .env):"
        if [ -f .env ]; then
            local email=$(grep "^SUPERUSER_EMAIL=" .env | cut -d'=' -f2)
            local password=$(grep "^SUPERUSER_PASSWORD=" .env | cut -d'=' -f2)
            if [ -n "$email" ] && [ -n "$password" ]; then
                echo -e "  Email:    ${YELLOW}$email${NC}"
                echo -e "  Password: ${YELLOW}$password${NC}"
            fi
        fi
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
        print_info "Install manually with: make pre-commit-install"
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

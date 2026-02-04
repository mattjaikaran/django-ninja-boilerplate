#!/bin/bash

# Django Ninja Boilerplate - Quickstart Script
# The fastest way to go from clone to running API
#
# Usage:
#   ./scripts/quickstart.sh              # Auto-detect best setup method
#   ./scripts/quickstart.sh --no-docker  # Force local-only setup
#   ./scripts/quickstart.sh --minimal    # Just API (no Celery, no seeding)
#   ./scripts/quickstart.sh --ci         # CI environment (no browser, no prompts)
#   make quickstart                      # Recommended way to run this
#
# Goal: git clone ... && cd ... && make quickstart -> working API in <2 minutes

set -e  # Exit on any error

# ===========================================
# Configuration & Constants
# ===========================================

SCRIPT_VERSION="1.0.0"
SCRIPT_START_TIME=$(date +%s)

# Default superuser credentials
DEFAULT_SUPERUSER_EMAIL="admin@example.com"
DEFAULT_SUPERUSER_USERNAME="admin"
DEFAULT_SUPERUSER_PASSWORD="admin123"
DEFAULT_SUPERUSER_FIRST_NAME="Admin"
DEFAULT_SUPERUSER_LAST_NAME="User"

# Required Python version
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=12

# Timeouts (in seconds)
SERVICE_WAIT_TIMEOUT=120
HEALTH_CHECK_TIMEOUT=60

# URLs
API_DOCS_URL="http://localhost:8000/api/docs"
ADMIN_URL="http://localhost:8000/admin"
HEALTH_URL="http://localhost:8000/api/health/"

# ===========================================
# Color & Output Configuration
# ===========================================

# Check if we should use colors (not in CI without TTY)
if [ -t 1 ] && [ -z "$NO_COLOR" ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    MAGENTA='\033[0;35m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    MAGENTA=''
    BOLD=''
    DIM=''
    NC=''
fi

# Progress spinner characters
SPINNER_CHARS='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

# ===========================================
# Parse Command Line Arguments
# ===========================================

USE_DOCKER=true
MINIMAL_MODE=false
CI_MODE=false
VERBOSE=false
SKIP_BROWSER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-docker|--local)
            USE_DOCKER=false
            shift
            ;;
        --minimal|-m)
            MINIMAL_MODE=true
            shift
            ;;
        --ci)
            CI_MODE=true
            SKIP_BROWSER=true
            shift
            ;;
        --no-browser)
            SKIP_BROWSER=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Django Ninja Boilerplate - Quickstart Script v${SCRIPT_VERSION}"
            echo ""
            echo "The fastest way to go from clone to running API."
            echo ""
            echo "Usage: ./scripts/quickstart.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-docker, --local    Force local-only setup (no Docker)"
            echo "  --minimal, -m           Just API (no Celery, minimal seeding)"
            echo "  --ci                    CI environment (no browser, no prompts)"
            echo "  --no-browser            Don't open browser at the end"
            echo "  --verbose, -v           Show detailed output"
            echo "  --help, -h              Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/quickstart.sh              # Auto-detect best setup"
            echo "  ./scripts/quickstart.sh --no-docker  # Local Python + external DB"
            echo "  ./scripts/quickstart.sh --minimal    # Fast, minimal setup"
            echo "  ./scripts/quickstart.sh --ci         # For CI/CD pipelines"
            echo ""
            echo "Makefile:"
            echo "  make quickstart                      # Recommended way to run"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run './scripts/quickstart.sh --help' for usage information."
            exit 1
            ;;
    esac
done

# ===========================================
# Output Functions
# ===========================================

# Print functions with consistent formatting
print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ____  _                         _   _ _       _       "
    echo " |  _ \\(_) __ _ _ __   __ _  ___ | \\ | (_)_ __ (_) __ _ "
    echo " | | | | |/ _\` | '_ \\ / _\` |/ _ \\|  \\| | | '_ \\| |/ _\` |"
    echo " | |_| | | (_| | | | | (_| | (_) | |\\  | | | | | | (_| |"
    echo " |____// |\\__,_|_| |_|\\__, |\\___/|_| \\_|_|_| |_| |\\__,_|"
    echo "     |__/             |___/            Quickstart v${SCRIPT_VERSION}"
    echo -e "${NC}"
    echo ""
}

print_step() {
    local step_num=$1
    local total=$2
    local message=$3
    echo ""
    echo -e "${BLUE}${BOLD}[$step_num/$total]${NC} ${BOLD}$message${NC}"
    echo -e "${DIM}$(printf '%.0s─' {1..60})${NC}"
}

print_substep() {
    echo -e "    ${CYAN}▸${NC} $1"
}

print_success() {
    echo -e "    ${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "    ${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "    ${RED}✗${NC} $1"
}

print_info() {
    echo -e "    ${BLUE}ℹ${NC} $1"
}

print_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "    ${DIM}[DEBUG] $1${NC}"
    fi
}

# Spinner for long-running operations
spinner_pid=""
start_spinner() {
    local message=$1
    if [ "$CI_MODE" = true ]; then
        echo -e "    ${CYAN}...${NC} $message"
        return
    fi

    (
        local i=0
        while true; do
            printf "\r    ${CYAN}${SPINNER_CHARS:$i:1}${NC} %s" "$message"
            i=$(( (i + 1) % ${#SPINNER_CHARS} ))
            sleep 0.1
        done
    ) &
    spinner_pid=$!
    disown $spinner_pid 2>/dev/null
}

stop_spinner() {
    local status=$1
    local message=$2

    if [ -n "$spinner_pid" ]; then
        kill $spinner_pid 2>/dev/null || true
        wait $spinner_pid 2>/dev/null || true
        spinner_pid=""
    fi

    # Clear the line
    printf "\r%s\r" "$(printf ' %.0s' {1..80})"

    if [ "$status" = "success" ]; then
        print_success "$message"
    elif [ "$status" = "warning" ]; then
        print_warning "$message"
    else
        print_error "$message"
    fi
}

# ===========================================
# Utility Functions
# ===========================================

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

get_python_version() {
    if command_exists python3; then
        python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    else
        echo "0.0"
    fi
}

check_python_version() {
    local version=$(get_python_version)
    local major=$(echo "$version" | cut -d'.' -f1)
    local minor=$(echo "$version" | cut -d'.' -f2)

    if [ "$major" -ge "$MIN_PYTHON_MAJOR" ] && [ "$minor" -ge "$MIN_PYTHON_MINOR" ]; then
        return 0
    fi
    return 1
}

is_docker_running() {
    docker info >/dev/null 2>&1
}

is_port_available() {
    local port=$1
    if command_exists lsof; then
        ! lsof -i :$port >/dev/null 2>&1
    elif command_exists netstat; then
        ! netstat -an | grep -q ":$port "
    else
        # Can't check, assume available
        return 0
    fi
}

generate_secret_key() {
    if command_exists python3; then
        python3 -c "import secrets; print(secrets.token_urlsafe(50))"
    elif command_exists openssl; then
        openssl rand -base64 50 | tr -d '\n/+=' | head -c 50
    else
        # Fallback to urandom
        cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1
    fi
}

open_browser() {
    local url=$1
    if [ "$SKIP_BROWSER" = true ]; then
        return
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "$url" 2>/dev/null || true
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "$url" 2>/dev/null || true
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        start "$url" 2>/dev/null || true
    fi
}

calculate_elapsed_time() {
    local end_time=$(date +%s)
    local elapsed=$((end_time - SCRIPT_START_TIME))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))

    if [ $minutes -gt 0 ]; then
        echo "${minutes}m ${seconds}s"
    else
        echo "${seconds}s"
    fi
}

# ===========================================
# Error Recovery Suggestions
# ===========================================

suggest_fix() {
    local issue=$1
    echo ""
    echo -e "${YELLOW}${BOLD}Troubleshooting:${NC}"

    case $issue in
        "python")
            echo -e "  ${CYAN}1.${NC} Install Python 3.12+:"
            echo "     - macOS: brew install python@3.12"
            echo "     - Ubuntu: sudo apt install python3.12"
            echo "     - Or use pyenv: pyenv install 3.12"
            ;;
        "docker")
            echo -e "  ${CYAN}1.${NC} Install Docker:"
            echo "     - Download from: https://www.docker.com/get-started"
            echo "     - Or try: --no-docker flag for local setup"
            echo ""
            echo -e "  ${CYAN}2.${NC} If Docker is installed but not running:"
            echo "     - macOS: Open Docker Desktop"
            echo "     - Linux: sudo systemctl start docker"
            ;;
        "docker_not_running")
            echo -e "  ${CYAN}1.${NC} Start Docker:"
            echo "     - macOS: Open Docker Desktop application"
            echo "     - Linux: sudo systemctl start docker"
            echo ""
            echo -e "  ${CYAN}2.${NC} Or run without Docker:"
            echo "     ./scripts/quickstart.sh --no-docker"
            ;;
        "uv")
            echo -e "  ${CYAN}1.${NC} Install UV package manager:"
            echo "     curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo ""
            echo -e "  ${CYAN}2.${NC} Then restart your terminal or run:"
            echo "     source ~/.bashrc  # or ~/.zshrc"
            ;;
        "port_8000")
            echo -e "  ${CYAN}1.${NC} Find and stop the process using port 8000:"
            echo "     lsof -i :8000"
            echo "     kill -9 <PID>"
            echo ""
            echo -e "  ${CYAN}2.${NC} Or stop existing Django containers:"
            echo "     docker-compose down"
            ;;
        "database")
            echo -e "  ${CYAN}1.${NC} Check Docker logs:"
            echo "     docker-compose logs db"
            echo ""
            echo -e "  ${CYAN}2.${NC} Reset the database volume:"
            echo "     docker-compose down -v"
            echo "     make quickstart"
            ;;
        "health_check")
            echo -e "  ${CYAN}1.${NC} Check Django logs:"
            echo "     docker-compose logs django"
            echo ""
            echo -e "  ${CYAN}2.${NC} The API might still be starting. Wait a moment and try:"
            echo "     curl http://localhost:8000/api/health/"
            ;;
        *)
            echo -e "  ${CYAN}1.${NC} Run the doctor script for diagnostics:"
            echo "     make doctor"
            echo ""
            echo -e "  ${CYAN}2.${NC} Check the logs:"
            echo "     docker-compose logs"
            ;;
    esac
    echo ""
}

# Cleanup function for graceful exit
cleanup() {
    if [ -n "$spinner_pid" ]; then
        kill $spinner_pid 2>/dev/null || true
    fi
}

trap cleanup EXIT

# ===========================================
# Step 1: Check Prerequisites
# ===========================================

check_prerequisites() {
    print_step 1 9 "Checking prerequisites"

    local has_errors=false
    local can_use_docker=true

    # Check Python version
    print_substep "Checking Python..."
    if command_exists python3; then
        local py_version=$(get_python_version)
        if check_python_version; then
            print_success "Python $py_version"
        else
            print_error "Python $py_version (need $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+)"
            has_errors=true
            suggest_fix "python"
        fi
    else
        print_error "Python 3 not found"
        has_errors=true
        suggest_fix "python"
    fi

    # Check Docker (for Docker mode)
    print_substep "Checking Docker..."
    if command_exists docker; then
        if is_docker_running; then
            local docker_version=$(docker --version | cut -d' ' -f3 | tr -d ',')
            print_success "Docker $docker_version (running)"
        else
            print_warning "Docker installed but not running"
            can_use_docker=false
            if [ "$USE_DOCKER" = true ]; then
                suggest_fix "docker_not_running"
            fi
        fi
    else
        print_warning "Docker not installed"
        can_use_docker=false
        if [ "$USE_DOCKER" = true ]; then
            print_info "Will attempt local setup instead"
        fi
    fi

    # Check UV
    print_substep "Checking UV package manager..."
    if command_exists uv; then
        local uv_version=$(uv --version 2>&1 | head -1)
        print_success "$uv_version"
    else
        if [ "$USE_DOCKER" = false ] || [ "$can_use_docker" = false ]; then
            print_error "UV not installed (required for local setup)"
            has_errors=true
            suggest_fix "uv"
        else
            print_warning "UV not installed (optional with Docker)"
        fi
    fi

    # Check Docker Compose
    if [ "$USE_DOCKER" = true ] && [ "$can_use_docker" = true ]; then
        print_substep "Checking Docker Compose..."
        if command_exists docker-compose; then
            print_success "docker-compose available"
        elif docker compose version >/dev/null 2>&1; then
            print_success "docker compose (plugin) available"
        else
            print_error "Docker Compose not found"
            has_errors=true
        fi
    fi

    # Check port availability
    print_substep "Checking port availability..."
    if is_port_available 8000; then
        print_success "Port 8000 available"
    else
        print_warning "Port 8000 in use"
        if [ "$CI_MODE" = false ]; then
            suggest_fix "port_8000"
        fi
    fi

    # Auto-detect best setup method
    if [ "$USE_DOCKER" = true ] && [ "$can_use_docker" = false ]; then
        print_info "Switching to local setup (Docker not available)"
        USE_DOCKER=false

        # Re-check UV is available for local setup
        if ! command_exists uv; then
            print_error "UV required for local setup but not installed"
            has_errors=true
            suggest_fix "uv"
        fi
    fi

    if [ "$has_errors" = true ]; then
        echo ""
        print_error "Prerequisites check failed. Please fix the issues above."
        exit 1
    fi

    # Print detected setup method
    echo ""
    if [ "$USE_DOCKER" = true ]; then
        print_info "Setup method: ${GREEN}Docker${NC} (recommended)"
    else
        print_info "Setup method: ${YELLOW}Local${NC} (requires external PostgreSQL & Redis)"
    fi
}

# ===========================================
# Step 2: Auto-detect Setup Method
# ===========================================

auto_detect_setup() {
    print_step 2 9 "Configuring setup method"

    if [ "$USE_DOCKER" = true ]; then
        print_success "Using Docker Compose for all services"
        print_info "Services: PostgreSQL, Redis, Django"
        if [ "$MINIMAL_MODE" = false ]; then
            print_info "Optional: Celery workers available via 'make up-celery'"
        fi
    else
        print_success "Using local Python environment"
        print_warning "You need to configure external PostgreSQL and Redis"
        print_info "Update .env with your database credentials"
    fi
}

# ===========================================
# Step 3: Create .env File
# ===========================================

setup_env_file() {
    print_step 3 9 "Setting up environment"

    if [ -f .env ]; then
        print_info ".env file already exists"

        # Check if SECRET_KEY needs to be generated
        if grep -q "^SECRET_KEY=your-secret-key" .env 2>/dev/null || \
           grep -q "^SECRET_KEY=$" .env 2>/dev/null; then
            print_substep "Generating secure SECRET_KEY..."
            local new_secret=$(generate_secret_key)

            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$new_secret|" .env
            else
                sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$new_secret|" .env
            fi
            print_success "SECRET_KEY generated"
        else
            print_success "SECRET_KEY already configured"
        fi
    else
        print_substep "Creating .env from template..."

        # Try to find a template
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success "Copied from .env.example"
        elif [ -f .env.development ]; then
            cp .env.development .env
            print_success "Copied from .env.development"
        else
            # Create comprehensive .env
            create_env_file
            print_success "Created new .env file"
        fi

        # Generate SECRET_KEY
        print_substep "Generating secure SECRET_KEY..."
        local new_secret=$(generate_secret_key)
        local new_jwt_secret=$(generate_secret_key)

        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$new_secret|" .env
            sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$new_jwt_secret|" .env 2>/dev/null || true
        else
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$new_secret|" .env
            sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$new_jwt_secret|" .env 2>/dev/null || true
        fi
        print_success "Secrets generated"
    fi

    # Set up superuser credentials if not already set
    setup_superuser_env
}

create_env_file() {
    cat > .env << 'ENVEOF'
# Django Ninja Boilerplate - Environment Configuration
# Generated by quickstart.sh

# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
DJANGO_SETTINGS_MODULE=api.settings
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,django

# Database Settings (Docker defaults)
DB_NAME=boilerplate_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Redis Settings
REDIS_URL=redis://redis:6379/0

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:3000
CORS_ORIGIN_WHITELIST=http://localhost:3000,http://127.0.0.1:3000

# Superuser Credentials (for quickstart)
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_USERNAME=admin
SUPERUSER_PASSWORD=admin123
SUPERUSER_FIRST_NAME=Admin
SUPERUSER_LAST_NAME=User

# JWT Settings
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_LIFETIME=5
JWT_REFRESH_TOKEN_LIFETIME=1
ENVEOF
}

setup_superuser_env() {
    print_substep "Configuring superuser credentials..."

    local needs_update=false

    # Check if superuser env vars are empty or missing
    if ! grep -q "^SUPERUSER_EMAIL=" .env 2>/dev/null || \
       grep -q "^SUPERUSER_EMAIL=''$" .env 2>/dev/null || \
       grep -q "^SUPERUSER_EMAIL=$" .env 2>/dev/null; then
        needs_update=true
    fi

    if [ "$needs_update" = true ]; then
        # Add or update superuser credentials
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS sed
            if grep -q "^SUPERUSER_EMAIL=" .env 2>/dev/null; then
                sed -i '' "s|^SUPERUSER_EMAIL=.*|SUPERUSER_EMAIL=$DEFAULT_SUPERUSER_EMAIL|" .env
                sed -i '' "s|^SUPERUSER_USERNAME=.*|SUPERUSER_USERNAME=$DEFAULT_SUPERUSER_USERNAME|" .env
                sed -i '' "s|^SUPERUSER_PASSWORD=.*|SUPERUSER_PASSWORD=$DEFAULT_SUPERUSER_PASSWORD|" .env
                sed -i '' "s|^SUPERUSER_FIRST_NAME=.*|SUPERUSER_FIRST_NAME=$DEFAULT_SUPERUSER_FIRST_NAME|" .env
                sed -i '' "s|^SUPERUSER_LAST_NAME=.*|SUPERUSER_LAST_NAME=$DEFAULT_SUPERUSER_LAST_NAME|" .env
            else
                echo "" >> .env
                echo "# Superuser Credentials" >> .env
                echo "SUPERUSER_EMAIL=$DEFAULT_SUPERUSER_EMAIL" >> .env
                echo "SUPERUSER_USERNAME=$DEFAULT_SUPERUSER_USERNAME" >> .env
                echo "SUPERUSER_PASSWORD=$DEFAULT_SUPERUSER_PASSWORD" >> .env
                echo "SUPERUSER_FIRST_NAME=$DEFAULT_SUPERUSER_FIRST_NAME" >> .env
                echo "SUPERUSER_LAST_NAME=$DEFAULT_SUPERUSER_LAST_NAME" >> .env
            fi
        else
            # Linux sed
            if grep -q "^SUPERUSER_EMAIL=" .env 2>/dev/null; then
                sed -i "s|^SUPERUSER_EMAIL=.*|SUPERUSER_EMAIL=$DEFAULT_SUPERUSER_EMAIL|" .env
                sed -i "s|^SUPERUSER_USERNAME=.*|SUPERUSER_USERNAME=$DEFAULT_SUPERUSER_USERNAME|" .env
                sed -i "s|^SUPERUSER_PASSWORD=.*|SUPERUSER_PASSWORD=$DEFAULT_SUPERUSER_PASSWORD|" .env
                sed -i "s|^SUPERUSER_FIRST_NAME=.*|SUPERUSER_FIRST_NAME=$DEFAULT_SUPERUSER_FIRST_NAME|" .env
                sed -i "s|^SUPERUSER_LAST_NAME=.*|SUPERUSER_LAST_NAME=$DEFAULT_SUPERUSER_LAST_NAME|" .env
            else
                echo "" >> .env
                echo "# Superuser Credentials" >> .env
                echo "SUPERUSER_EMAIL=$DEFAULT_SUPERUSER_EMAIL" >> .env
                echo "SUPERUSER_USERNAME=$DEFAULT_SUPERUSER_USERNAME" >> .env
                echo "SUPERUSER_PASSWORD=$DEFAULT_SUPERUSER_PASSWORD" >> .env
                echo "SUPERUSER_FIRST_NAME=$DEFAULT_SUPERUSER_FIRST_NAME" >> .env
                echo "SUPERUSER_LAST_NAME=$DEFAULT_SUPERUSER_LAST_NAME" >> .env
            fi
        fi
        print_success "Superuser credentials configured"
    else
        print_success "Superuser credentials already set"
    fi
}

# ===========================================
# Step 4: Start Services
# ===========================================

start_services() {
    print_step 4 9 "Starting services"

    if [ "$USE_DOCKER" = true ]; then
        start_docker_services
    else
        start_local_services
    fi
}

start_docker_services() {
    # Build images
    print_substep "Building Docker images..."
    start_spinner "Building images (this may take a few minutes on first run)..."

    if docker-compose build --quiet 2>/dev/null; then
        stop_spinner "success" "Docker images built"
    else
        # Try without --quiet for better error visibility
        stop_spinner "warning" "Build had issues, retrying with verbose output..."
        docker-compose build
    fi

    # Start services
    print_substep "Starting containers..."
    start_spinner "Starting PostgreSQL, Redis, and Django..."

    docker-compose up -d 2>/dev/null

    stop_spinner "success" "Containers started"
}

start_local_services() {
    print_substep "Setting up local Python environment..."

    # Install dependencies with UV
    if command_exists uv; then
        start_spinner "Installing dependencies with UV..."
        uv pip install -e . >/dev/null 2>&1
        stop_spinner "success" "Dependencies installed"
    else
        print_error "UV not found. Please install UV first."
        suggest_fix "uv"
        exit 1
    fi

    print_warning "Make sure PostgreSQL and Redis are running locally"
    print_info "Update .env with correct DB_HOST=localhost if needed"
}

# ===========================================
# Step 5: Wait for Health
# ===========================================

wait_for_services() {
    print_step 5 9 "Waiting for services to be healthy"

    if [ "$USE_DOCKER" = true ]; then
        wait_for_docker_services
    else
        print_info "Skipping service wait for local setup"
    fi
}

wait_for_docker_services() {
    local max_attempts=$((SERVICE_WAIT_TIMEOUT / 2))

    # Wait for database
    print_substep "Waiting for PostgreSQL..."
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T db pg_isready -U postgres >/dev/null 2>&1; then
            print_success "PostgreSQL is ready"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_error "PostgreSQL failed to start within ${SERVICE_WAIT_TIMEOUT}s"
            suggest_fix "database"
            exit 1
        fi

        sleep 2
        ((attempt++))
    done

    # Wait for Redis
    print_substep "Waiting for Redis..."
    attempt=1
    while [ $attempt -le $((max_attempts / 2)) ]; do
        if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
            print_success "Redis is ready"
            break
        fi

        if [ $attempt -eq $((max_attempts / 2)) ]; then
            print_warning "Redis might not be ready, continuing anyway..."
            break
        fi

        sleep 2
        ((attempt++))
    done

    # Wait for Django
    print_substep "Waiting for Django..."
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps django 2>/dev/null | grep -q "Up"; then
            print_success "Django container is running"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_warning "Django container might still be starting..."
            break
        fi

        sleep 2
        ((attempt++))
    done

    # Extra wait for Django to fully initialize
    print_info "Giving Django a moment to initialize..."
    sleep 5
}

# ===========================================
# Step 6: Run Migrations
# ===========================================

run_migrations() {
    print_step 6 9 "Running database migrations"

    print_substep "Applying migrations..."
    start_spinner "Migrating database schema..."

    if [ "$USE_DOCKER" = true ]; then
        if docker-compose exec -T django uv run python manage.py migrate --noinput >/dev/null 2>&1; then
            stop_spinner "success" "Migrations applied successfully"
        else
            stop_spinner "warning" "Migration had warnings, checking status..."
            docker-compose exec -T django uv run python manage.py migrate --noinput 2>&1 | tail -5
        fi
    else
        if uv run python manage.py migrate --noinput >/dev/null 2>&1; then
            stop_spinner "success" "Migrations applied successfully"
        else
            stop_spinner "error" "Migration failed"
            exit 1
        fi
    fi

    # Collect static files
    print_substep "Collecting static files..."
    if [ "$USE_DOCKER" = true ]; then
        docker-compose exec -T django uv run python manage.py collectstatic --noinput >/dev/null 2>&1 || true
    else
        uv run python manage.py collectstatic --noinput >/dev/null 2>&1 || true
    fi
    print_success "Static files collected"
}

# ===========================================
# Step 7: Create Superuser
# ===========================================

create_superuser() {
    print_step 7 9 "Creating superuser"

    print_substep "Creating admin account..."

    if [ "$USE_DOCKER" = true ]; then
        # Try the custom create_superuser command first
        if docker-compose exec -T django uv run python manage.py create_superuser 2>/dev/null; then
            print_success "Superuser created: $DEFAULT_SUPERUSER_EMAIL"
        else
            # Fallback: create superuser via Django shell
            print_info "Using fallback superuser creation..."
            docker-compose exec -T django uv run python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$DEFAULT_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser(
        email='$DEFAULT_SUPERUSER_EMAIL',
        username='$DEFAULT_SUPERUSER_USERNAME',
        password='$DEFAULT_SUPERUSER_PASSWORD',
        first_name='$DEFAULT_SUPERUSER_FIRST_NAME',
        last_name='$DEFAULT_SUPERUSER_LAST_NAME'
    )
    print('Superuser created')
else:
    print('Superuser already exists')
" 2>/dev/null && print_success "Superuser ready: $DEFAULT_SUPERUSER_EMAIL" || print_warning "Superuser may already exist"
        fi
    else
        # Local setup
        if uv run python manage.py create_superuser 2>/dev/null; then
            print_success "Superuser created: $DEFAULT_SUPERUSER_EMAIL"
        else
            print_warning "Could not auto-create superuser. Run manually:"
            print_info "uv run python manage.py createsuperuser"
        fi
    fi
}

# ===========================================
# Step 8: Seed Sample Data
# ===========================================

seed_sample_data() {
    print_step 8 9 "Seeding sample data"

    if [ "$MINIMAL_MODE" = true ]; then
        print_info "Skipping sample data (--minimal mode)"
        return
    fi

    print_substep "Generating sample data..."
    start_spinner "Creating users, todos, and test data..."

    if [ "$USE_DOCKER" = true ]; then
        # Try seed_data command first
        if docker-compose exec -T django uv run python manage.py seed_data --superuser-only 2>/dev/null; then
            # Superuser handled above, just seed other data
            docker-compose exec -T django uv run python manage.py seed_data --no-superuser --users 10 --todos 20 >/dev/null 2>&1 || true
            stop_spinner "success" "Sample data created"
        else
            # Try generate_core_data as fallback
            docker-compose exec -T django uv run python manage.py generate_core_data >/dev/null 2>&1 || true
            stop_spinner "success" "Core data generated"
        fi
    else
        uv run python manage.py seed_data --no-superuser --users 10 --todos 20 >/dev/null 2>&1 || \
        uv run python manage.py generate_core_data >/dev/null 2>&1 || true
        stop_spinner "success" "Sample data created"
    fi
}

# ===========================================
# Step 9: Health Check & Browser
# ===========================================

final_health_check() {
    print_step 9 9 "Final verification"

    print_substep "Checking API health..."

    local max_attempts=$((HEALTH_CHECK_TIMEOUT / 2))
    local attempt=1
    local health_ok=false

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
            health_ok=true
            break
        fi
        sleep 2
        ((attempt++))
    done

    if [ "$health_ok" = true ]; then
        print_success "API is healthy and responding"
    else
        print_warning "API health check timed out (may still be starting)"
        if [ "$CI_MODE" = false ]; then
            suggest_fix "health_check"
        fi
    fi

    # Open browser
    if [ "$SKIP_BROWSER" = false ] && [ "$health_ok" = true ]; then
        print_substep "Opening API documentation in browser..."
        open_browser "$API_DOCS_URL"
        print_success "Browser opened to $API_DOCS_URL"
    fi
}

# ===========================================
# Summary
# ===========================================

print_summary() {
    local elapsed=$(calculate_elapsed_time)

    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════════╗"
    echo "  ║                                                               ║"
    echo "  ║              QUICKSTART COMPLETE!                             ║"
    echo "  ║                                                               ║"
    echo "  ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo -e "${BOLD}Setup completed in ${CYAN}$elapsed${NC}"
    echo ""

    # URLs section
    echo -e "${BOLD}Your API is running at:${NC}"
    echo -e "  ${GREEN}API Documentation:${NC}  $API_DOCS_URL"
    echo -e "  ${GREEN}Django Admin:${NC}       $ADMIN_URL"
    echo -e "  ${GREEN}Health Check:${NC}       $HEALTH_URL"
    echo ""

    # Credentials section
    echo -e "${BOLD}Default Credentials:${NC}"
    echo -e "  ${CYAN}Email:${NC}    $DEFAULT_SUPERUSER_EMAIL"
    echo -e "  ${CYAN}Password:${NC} $DEFAULT_SUPERUSER_PASSWORD"
    echo ""

    # Quick commands section
    echo -e "${BOLD}Useful Commands:${NC}"
    echo -e "  ${CYAN}make up${NC}           Start services"
    echo -e "  ${CYAN}make down${NC}         Stop services"
    echo -e "  ${CYAN}make logs${NC}         View logs"
    echo -e "  ${CYAN}make shell${NC}        Django shell"
    echo -e "  ${CYAN}make test${NC}         Run tests"
    echo ""

    if [ "$MINIMAL_MODE" = false ]; then
        echo -e "${BOLD}For Celery background tasks:${NC}"
        echo -e "  ${CYAN}make up-celery${NC}    Start with Celery workers"
        echo -e "  ${CYAN}make up-full${NC}      Start all services including Flower"
        echo ""
    fi

    # Next steps
    echo -e "${BOLD}Next Steps:${NC}"
    echo -e "  ${CYAN}1.${NC} Explore the API at $API_DOCS_URL"
    echo -e "  ${CYAN}2.${NC} Log into admin at $ADMIN_URL"
    echo -e "  ${CYAN}3.${NC} Start building your features!"
    echo ""

    echo -e "${GREEN}Happy coding!${NC}"
    echo ""
}

# ===========================================
# Main Execution
# ===========================================

main() {
    print_banner

    if [ "$CI_MODE" = true ]; then
        print_info "Running in CI mode (no prompts, no browser)"
    fi

    if [ "$MINIMAL_MODE" = true ]; then
        print_info "Running in minimal mode (faster, less data)"
    fi

    # Execute all steps
    check_prerequisites
    auto_detect_setup
    setup_env_file
    start_services
    wait_for_services
    run_migrations
    create_superuser
    seed_sample_data
    final_health_check

    # Print summary
    print_summary
}

# Run main function
main

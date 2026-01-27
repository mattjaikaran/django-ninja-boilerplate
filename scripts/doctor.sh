#!/bin/bash

# Environment validation script for Django Ninja Boilerplate
# Run with: make doctor or ./scripts/doctor.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
WARN=0
FAIL=0

# Print functions
print_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS++))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARN++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAIL++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if port is available
port_available() {
    if command_exists lsof; then
        ! lsof -i :$1 >/dev/null 2>&1
    elif command_exists netstat; then
        ! netstat -an | grep -q ":$1 "
    else
        # Can't check, assume available
        return 0
    fi
}

# Header
echo ""
echo "=========================================="
echo "  Django Ninja Boilerplate - Doctor"
echo "=========================================="
echo ""

# ===========================================
# System Requirements
# ===========================================
echo "System Requirements"
echo "-------------------"

# Python version
print_check "Python version..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        print_pass "Python $PYTHON_VERSION (>= 3.11 required)"
    else
        print_fail "Python $PYTHON_VERSION (>= 3.11 required)"
    fi
else
    print_fail "Python 3 not found"
fi

# UV package manager
print_check "UV package manager..."
if command_exists uv; then
    UV_VERSION=$(uv --version 2>&1 | head -1)
    print_pass "$UV_VERSION"
else
    print_warn "UV not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Docker
print_check "Docker..."
if command_exists docker; then
    if docker info >/dev/null 2>&1; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_pass "Docker $DOCKER_VERSION (running)"
    else
        print_fail "Docker installed but not running. Start Docker Desktop or daemon."
    fi
else
    print_fail "Docker not installed"
fi

# Docker Compose
print_check "Docker Compose..."
if command_exists docker-compose; then
    DC_VERSION=$(docker-compose --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    print_pass "Docker Compose $DC_VERSION"
elif docker compose version >/dev/null 2>&1; then
    DC_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    print_pass "Docker Compose $DC_VERSION (plugin)"
else
    print_fail "Docker Compose not installed"
fi

# Make
print_check "Make..."
if command_exists make; then
    print_pass "Make available"
else
    print_warn "Make not installed (optional but recommended)"
fi

# Git
print_check "Git..."
if command_exists git; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    print_pass "Git $GIT_VERSION"
else
    print_warn "Git not installed"
fi

echo ""

# ===========================================
# Port Availability
# ===========================================
echo "Port Availability"
echo "-----------------"

# PostgreSQL port
print_check "Port 5432 (PostgreSQL)..."
if port_available 5432; then
    print_pass "Port 5432 available"
else
    print_warn "Port 5432 in use (may conflict with local PostgreSQL)"
fi

# Redis port
print_check "Port 6379 (Redis)..."
if port_available 6379; then
    print_pass "Port 6379 available"
else
    print_warn "Port 6379 in use (may conflict with local Redis)"
fi

# Django port
print_check "Port 8000 (Django)..."
if port_available 8000; then
    print_pass "Port 8000 available"
else
    print_warn "Port 8000 in use"
fi

# Flower port (optional)
print_check "Port 5555 (Flower)..."
if port_available 5555; then
    print_pass "Port 5555 available"
else
    print_warn "Port 5555 in use (Flower monitoring won't be available)"
fi

echo ""

# ===========================================
# Project Configuration
# ===========================================
echo "Project Configuration"
echo "---------------------"

# .env file
print_check ".env file..."
if [ -f .env ]; then
    print_pass ".env file exists"

    # Check required variables
    print_check "Required environment variables..."
    MISSING_VARS=""
    for var in SECRET_KEY DB_NAME DB_USER DB_PASSWORD; do
        if ! grep -q "^${var}=" .env 2>/dev/null; then
            MISSING_VARS="$MISSING_VARS $var"
        fi
    done

    if [ -z "$MISSING_VARS" ]; then
        print_pass "All required variables present"
    else
        print_warn "Missing variables:$MISSING_VARS"
    fi

    # Check if SECRET_KEY is default
    if grep -q "^SECRET_KEY=your-secret-key" .env 2>/dev/null || grep -q "^SECRET_KEY=$" .env 2>/dev/null; then
        print_warn "SECRET_KEY is using default value. Generate a new one for production!"
    fi
else
    print_fail ".env file not found. Run: make setup-env or cp .env.example .env"
fi

# .env.example
print_check ".env.example file..."
if [ -f .env.example ]; then
    print_pass ".env.example exists"
else
    print_warn ".env.example not found"
fi

# pyproject.toml
print_check "pyproject.toml..."
if [ -f pyproject.toml ]; then
    print_pass "pyproject.toml exists"
else
    print_fail "pyproject.toml not found"
fi

# Dockerfile
print_check "Dockerfile..."
if [ -f Dockerfile ]; then
    print_pass "Dockerfile exists"
else
    print_fail "Dockerfile not found"
fi

# docker-compose.yml
print_check "docker-compose.yml..."
if [ -f docker-compose.yml ]; then
    print_pass "docker-compose.yml exists"
else
    print_fail "docker-compose.yml not found"
fi

echo ""

# ===========================================
# Service Connectivity (if running)
# ===========================================
echo "Service Connectivity"
echo "--------------------"

# Check if Docker services are running
if docker-compose ps 2>/dev/null | grep -q "Up"; then
    print_info "Docker services detected, checking connectivity..."

    # Database connection
    print_check "Database connection..."
    if docker-compose exec -T db pg_isready -U postgres >/dev/null 2>&1; then
        print_pass "PostgreSQL is accepting connections"
    else
        print_fail "PostgreSQL not responding"
    fi

    # Redis connection
    print_check "Redis connection..."
    if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        print_pass "Redis is responding"
    else
        print_fail "Redis not responding"
    fi

    # Django health check
    print_check "Django health endpoint..."
    if curl -sf http://localhost:8000/api/health/ >/dev/null 2>&1; then
        print_pass "Django API is healthy"
    else
        print_warn "Django API not responding (may still be starting)"
    fi
else
    print_info "Docker services not running. Start with: make up"
fi

echo ""

# ===========================================
# Summary
# ===========================================
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
echo -e "  ${GREEN}Passed:${NC}  $PASS"
echo -e "  ${YELLOW}Warnings:${NC} $WARN"
echo -e "  ${RED}Failed:${NC}  $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    if [ $WARN -eq 0 ]; then
        echo -e "${GREEN}All checks passed! Your environment is ready.${NC}"
    else
        echo -e "${YELLOW}Environment is mostly ready with some warnings.${NC}"
    fi
    exit 0
else
    echo -e "${RED}Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi

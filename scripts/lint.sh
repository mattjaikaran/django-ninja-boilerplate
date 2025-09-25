#!/bin/bash

# Code quality and linting script for Django Ninja Boilerplate

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to run linting checks
run_checks() {
    local exit_code=0
    
    print_info "Running code quality checks..."
    
    # Run Ruff linting
    print_info "Running Ruff linting..."
    if uv run ruff check .; then
        print_success "Ruff linting passed!"
    else
        print_error "Ruff linting failed!"
        exit_code=1
    fi
    
    # Check code formatting
    print_info "Checking code formatting..."
    if uv run ruff format --check .; then
        print_success "Code formatting is correct!"
    else
        print_error "Code formatting issues found!"
        print_info "Run 'make format' to fix formatting issues"
        exit_code=1
    fi
    
    # Run type checking if mypy is available
    if command -v mypy >/dev/null 2>&1; then
        print_info "Running type checking..."
        if uv run mypy .; then
            print_success "Type checking passed!"
        else
            print_warning "Type checking issues found!"
            # Don't fail on mypy issues for now
        fi
    else
        print_warning "MyPy not available, skipping type checking"
    fi
    
    return $exit_code
}

# Function to fix auto-fixable issues
fix_issues() {
    print_info "Fixing auto-fixable issues..."
    
    # Fix linting issues
    print_info "Fixing linting issues..."
    uv run ruff check --fix .
    
    # Format code
    print_info "Formatting code..."
    uv run ruff format .
    
    print_success "Auto-fix complete!"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [check|fix]"
    echo ""
    echo "Commands:"
    echo "  check  - Run all linting and formatting checks (default)"
    echo "  fix    - Fix auto-fixable issues and format code"
    echo ""
    echo "Examples:"
    echo "  $0       # Run checks"
    echo "  $0 check # Run checks"
    echo "  $0 fix   # Fix issues"
}

# Main execution
main() {
    local command="${1:-check}"
    
    case $command in
        check)
            run_checks
            ;;
        fix)
            fix_issues
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
#!/bin/bash

# Generate a secure Django SECRET_KEY

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to generate secret key using Python
generate_secret_key() {
    python3 -c "
import secrets
import string

# Generate a 50-character secret key
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
secret_key = ''.join(secrets.choice(alphabet) for i in range(50))
print(secret_key)
"
}

# Function to generate secret key using OpenSSL (fallback)
generate_secret_key_openssl() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-50
}

# Function to update .env file
update_env_file() {
    local new_key="$1"
    
    if [ -f .env ]; then
        # Check if SECRET_KEY already exists in .env
        if grep -q "^SECRET_KEY=" .env; then
            # Replace existing SECRET_KEY
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s/^SECRET_KEY=.*/SECRET_KEY=$new_key/" .env
            else
                # Linux
                sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$new_key/" .env
            fi
            print_success "Updated SECRET_KEY in .env file"
        else
            # Add SECRET_KEY to .env
            echo "SECRET_KEY=$new_key" >> .env
            print_success "Added SECRET_KEY to .env file"
        fi
    else
        # Create .env file with SECRET_KEY
        echo "SECRET_KEY=$new_key" > .env
        print_success "Created .env file with SECRET_KEY"
    fi
}

# Main execution
main() {
    local update_file=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --update-env)
                update_file=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [--update-env]"
                echo ""
                echo "Options:"
                echo "  --update-env    Update the .env file with the new secret key"
                echo "  -h, --help      Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                    # Just generate and display a secret key"
                echo "  $0 --update-env       # Generate and update .env file"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_info "Generating Django SECRET_KEY..."
    
    # Try to generate secret key with Python first
    if command -v python3 >/dev/null 2>&1; then
        secret_key=$(generate_secret_key)
    elif command -v openssl >/dev/null 2>&1; then
        print_info "Python3 not found, using OpenSSL as fallback..."
        secret_key=$(generate_secret_key_openssl)
    else
        echo "Error: Neither Python3 nor OpenSSL found. Cannot generate secret key."
        exit 1
    fi
    
    echo ""
    echo "Generated SECRET_KEY:"
    echo "$secret_key"
    echo ""
    
    if [ "$update_file" = true ]; then
        update_env_file "$secret_key"
    else
        print_info "To update your .env file automatically, run:"
        echo "  $0 --update-env"
        echo ""
        print_info "Or manually add this to your .env file:"
        echo "  SECRET_KEY=$secret_key"
    fi
}

# Run main function
main "$@"
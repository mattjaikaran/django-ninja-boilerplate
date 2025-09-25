#!/bin/bash

# Development entrypoint script

set -e

echo "Development mode: Installing dependencies..."

# Check if virtual environment exists and is working
if [ -d ".venv" ] && .venv/bin/python -c "import django" 2>/dev/null; then
    echo "Virtual environment already exists and working"
else
    echo "Virtual environment not found or broken, but dependencies should be installed by Dockerfile"
    echo "Dependencies will be available via the virtual environment created during build"
fi

# Add virtual environment to PATH
export PATH="/app/.venv/bin:$PATH"

# Wait for database and redis if they're needed
if [ "$1" = "python" ] && [[ "$2" == *"manage.py"* ]]; then
    echo "Waiting for database and redis..."
    if [ "$DB_HOST" ] && [ "$DB_PORT" ]; then
        while ! nc -z "$DB_HOST" "$DB_PORT"; do
            sleep 1
        done
        echo "Database is ready!"
    fi
    
    if [ "$REDIS_URL" ]; then
        REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
        REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        
        if [ "$REDIS_HOST" ] && [ "$REDIS_PORT" ]; then
            while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
                sleep 1
            done
            echo "Redis is ready!"
        fi
    fi
fi

# Execute the command
exec "$@"

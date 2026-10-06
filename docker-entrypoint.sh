#!/bin/bash

# Docker entrypoint script for Django application

set -e

# Function to wait for service to be ready
wait_for_service() {
    host="$1"
    port="$2"
    service_name="$3"

    echo "Waiting for $service_name at $host:$port..."
    while ! nc -z "$host" "$port"; do
        sleep 1
    done
    echo "$service_name is ready!"
}

# Wait for database
if [ "$DB_HOST" ] && [ "$DB_PORT" ]; then
    wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL"
fi

# Wait for Redis
if [ "$REDIS_URL" ]; then
    # Extract host and port from Redis URL
    REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    if [ "$REDIS_HOST" ] && [ "$REDIS_PORT" ]; then
        wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
    fi
fi

# Run Django migrations
echo "Running Django migrations..."
python manage.py migrate --noinput

# Create a superuser only when explicitly requested. Template credentials live
# in .env.example, so creating one unconditionally would provision a known
# admin account on any deployment that reuses that file.
if [ "$CREATE_SUPERUSER" = "true" ] && [ "$SUPERUSER_EMAIL" ] && [ "$SUPERUSER_PASSWORD" ]; then
    # Outside development, refuse passwords that were ever published in this
    # repository's templates and anything shorter than 12 characters.
    if [ "${ENVIRONMENT:-production}" != "development" ]; then
        case "$SUPERUSER_PASSWORD" in
            'Password123!' | admin123 | admin | password | changeme | CHANGE_ME)
                echo "Refusing to create superuser: SUPERUSER_PASSWORD is a published default." >&2
                exit 1
                ;;
        esac
        if [ "${#SUPERUSER_PASSWORD}" -lt 12 ]; then
            echo "Refusing to create superuser: SUPERUSER_PASSWORD must be at least 12 characters." >&2
            exit 1
        fi
    fi
    echo "Creating Django superuser..."
    python manage.py create_superuser 2>/dev/null || \
    echo "Superuser creation skipped (may already exist or missing env vars)"
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the main command
echo "Starting application..."
exec "$@"

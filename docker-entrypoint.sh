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

# Create superuser if it doesn't exist (using management command to avoid shell injection)
if [ "$SUPERUSER_EMAIL" ] && [ "$SUPERUSER_PASSWORD" ]; then
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

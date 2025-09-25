#!/bin/bash

# Script to run migrations with Docker and uv
echo "🚀 Running migrations for Django Ninja Boilerplate..."

# Make migrations for the new priority field
echo "📝 Creating migrations..."
docker-compose run --rm django python manage.py makemigrations

# Apply migrations
echo "⚡ Applying migrations..."
docker-compose run --rm django python manage.py migrate

echo "✅ Migrations completed!"

# Optional: Create superuser if needed
echo "👤 Creating superuser (optional)..."
docker-compose run --rm django python manage.py createsuperuser --noinput || echo "Superuser creation skipped"

echo "🎉 Setup complete! Your Django Ninja Boilerplate is ready with:"
echo "   ✓ PostgreSQL 17"
echo "   ✓ Professional decorators (@handle_exceptions, @log_api_call, etc.)"
echo "   ✓ Advanced search & filtering"
echo "   ✓ Pagination support"
echo "   ✓ Query optimizations"
echo "   ✓ No more try-except blocks"
echo "   ✓ Todo priority field added"

# Setup Guide

This document outlines the development setup process for the Django Ninja Boilerplate project.

## Quick Setup

Use the automated setup script for the fastest start:

```bash
./scripts/setup.sh
```

Or use make commands:

```bash
make setup
```

## Manual Setup Process

### 1. Clone and Navigate

```bash
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate
```

### 2. Environment Setup

```bash
# Create environment file
cp .env.example .env

# Edit .env with your database and secret key settings
```

### 3. Install Dependencies

Using uv (recommended):

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --dev
```

Using traditional Python virtual environment:

```bash
# Create virtual environment
python3 -m venv env

# Activate virtual environment
# On macOS and Linux:
source env/bin/activate
# On Windows:
# env\Scripts\activate

# Install dependencies with uv
uv sync --dev
```

### 4. Database Setup

```bash
# Run migrations and create superuser
uv run python manage.py migrate
uv run python manage.py create_superuser
```

### 5. Generate Secret Key

```bash
./scripts/generate_secret_key.sh --update-env
```

### 6. Start Development Server

```bash
# Using Docker (recommended)
make up

# Or locally
make local-run
```

## Creating New Apps

Use the extended startapp command that includes Django Ninja structure:

```bash
make startapp APP=myapp
```

This creates an app with the proper folder structure including:

- controllers/ for API endpoints
- schemas/ for Pydantic models
- admin/ for Django admin
- tests/ with factory-based testing

## Available Make Commands

See all available commands:

```bash
make help
```

Common commands:

- `make up` - Start development environment
- `make down` - Stop development environment
- `make test` - Run tests
- `make lint` - Check code quality
- `make format` - Format code
- `make migrate` - Run database migrations
- `make shell` - Open Django shell

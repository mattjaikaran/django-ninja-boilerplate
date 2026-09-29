# Setup Guide

This document outlines the development setup process for the Django Ninja Boilerplate project.

## Quick Setup

Use the automated setup script for the fastest start:

```bash
./scripts/setup.sh
```

Or use the just recipes:

```bash
just setup
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
uv sync --extra dev
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
uv sync --extra dev
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
just up

# Or locally
just legacy local-run
```

## Creating New Apps

Use the extended startapp command that includes Django Ninja structure:

```bash
just legacy startapp APP=myapp
```

This creates an app with the proper folder structure including:

- controllers/ for API endpoints
- schemas/ for Pydantic models
- admin/ for Django admin
- tests/ with factory-based testing

## Available Make Commands

See all available commands:

```bash
just help
```

Common commands:

- `just up` - Start development environment
- `just down` - Stop development environment
- `just test` - Run tests
- `just lint` - Check code quality
- `just format` - Format code
- `just migrate` - Run database migrations
- `just shell` - Open Django shell

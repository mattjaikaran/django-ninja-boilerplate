# Contributing to Django Ninja Boilerplate

Thank you for your interest in contributing to Django Ninja Boilerplate! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Getting Help](#getting-help)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone. Please:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **uv** - Fast Python package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker & Docker Compose** - For running services locally
- **Git** - For version control
- **Make** - For running project commands

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:

   ```bash
   git clone https://github.com/YOUR_USERNAME/django-ninja-boilerplate.git
   cd django-ninja-boilerplate
   ```

3. Add the upstream repository:

   ```bash
   git remote add upstream https://github.com/mattjaikaran/django-ninja-boilerplate.git
   ```

## Development Setup

### Quick Setup (Recommended)

The fastest way to get started is using our CLI tool:

```bash
# One-command setup
make setup

# Or use the CLI directly
./manage.py doctor  # Check your environment
```

### Manual Setup

If you prefer manual setup:

1. **Create and activate virtual environment:**

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   uv pip install -e ".[dev]"
   ```

3. **Set up environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

4. **Start required services:**

   ```bash
   docker-compose up -d postgres redis
   ```

5. **Run migrations:**

   ```bash
   python manage.py migrate
   ```

6. **Install pre-commit hooks:**

   ```bash
   pre-commit install
   ```

7. **Verify setup:**

   ```bash
   make test
   make lint
   ```

### Running the Development Server

```bash
# Start the Django development server
make run
# or
python manage.py runserver

# Access the API at http://localhost:8000
# API docs at http://localhost:8000/api/docs
```

## Code Style Guidelines

We use automated tools to maintain consistent code quality.

### Ruff (Linting & Formatting)

[Ruff](https://docs.astral.sh/ruff/) is our primary tool for linting and formatting Python code.

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .

# Or use Make commands
make lint      # Check linting
make format    # Auto-format code
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit to ensure code quality.

```bash
# Install hooks (one-time setup)
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

**Configured hooks include:**
- Ruff linting and formatting
- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON validation
- Large file prevention
- Secret detection

### Python Style Guidelines

Follow these conventions:

1. **Imports**: Use absolute imports, organized in sections (stdlib, third-party, local)
2. **Type Hints**: Use type hints for function signatures and class attributes
3. **Docstrings**: Use Google-style docstrings for public functions and classes
4. **Naming**:
   - `snake_case` for functions, variables, and modules
   - `PascalCase` for classes
   - `UPPER_SNAKE_CASE` for constants

**Example:**

```python
from typing import Optional

from django.db import models
from ninja import Schema

from app.core.models import BaseModel


class UserSchema(Schema):
    """Schema for user data.

    Attributes:
        id: The unique user identifier.
        email: The user's email address.
        name: The user's display name.
    """

    id: int
    email: str
    name: Optional[str] = None


def get_user_by_email(email: str) -> Optional[User]:
    """Retrieve a user by their email address.

    Args:
        email: The email address to search for.

    Returns:
        The User object if found, None otherwise.
    """
    return User.objects.filter(email=email).first()
```

### Django Ninja Guidelines

- Use `Schema` classes for request/response validation
- Organize routers by feature/domain
- Use appropriate HTTP status codes
- Document endpoints with docstrings

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-user-authentication`
- `fix/resolve-token-expiration-bug`
- `docs/update-api-reference`
- `refactor/simplify-database-queries`
- `test/add-integration-tests`

### Creating a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create your branch
git checkout -b feature/your-feature-name
```

### Commit Messages

Write clear, descriptive commit messages:

```
type: short description (50 chars or less)

Longer explanation if needed. Wrap at 72 characters.
Explain the problem this commit solves and why.

- Bullet points are fine
- Use present tense ("Add feature" not "Added feature")

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## Pull Request Process

### Before Submitting

1. **Sync your branch:**

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks:**

   ```bash
   make lint      # Linting passes
   make test      # Tests pass
   make format    # Code is formatted
   ```

3. **Update documentation** if needed

4. **Add/update tests** for your changes

### Submitting a PR

1. Push your branch to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request on GitHub

3. Fill out the PR template completely

4. Request review from maintainers

### PR Review Process

- PRs require at least one approval before merging
- Address all review comments
- Keep PRs focused and reasonably sized
- Squash commits if requested

### After Merge

```bash
# Update your local main
git checkout main
git pull upstream main

# Delete your branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

## Testing Requirements

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_users.py

# Run specific test
pytest tests/test_users.py::test_create_user -v

# Run with print output
pytest -s
```

### Writing Tests

1. **Location**: Place tests in the `tests/` directory
2. **Naming**: Use `test_` prefix for test files and functions
3. **Fixtures**: Use pytest fixtures for setup/teardown
4. **Coverage**: Aim for 80%+ coverage on new code

**Example:**

```python
import pytest
from django.test import Client

from users.models import User


@pytest.fixture
def api_client():
    """Create a test client."""
    return Client()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123"
    )


class TestUserAPI:
    """Tests for the User API endpoints."""

    def test_create_user(self, api_client, db):
        """Test user creation endpoint."""
        response = api_client.post(
            "/api/users/",
            data={"email": "new@example.com", "password": "newpass123"},
            content_type="application/json"
        )

        assert response.status_code == 201
        assert User.objects.filter(email="new@example.com").exists()

    def test_get_user(self, api_client, test_user):
        """Test retrieving a user."""
        response = api_client.get(f"/api/users/{test_user.id}/")

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
```

### Test Categories

- **Unit Tests**: Test individual functions/methods in isolation
- **Integration Tests**: Test component interactions
- **API Tests**: Test API endpoints end-to-end

## Documentation

### When to Update Docs

- Adding new features or endpoints
- Changing existing behavior
- Fixing unclear documentation
- Adding examples or tutorials

### Documentation Standards

- Use clear, concise language
- Include code examples where helpful
- Keep README.md up to date
- Document API changes in endpoint docstrings

## Getting Help

### Resources

- **Documentation**: Check the README and docs folder
- **Issues**: Search existing issues for similar problems
- **Discussions**: Use GitHub Discussions for questions

### Asking Questions

When asking for help:

1. Describe what you're trying to do
2. Show what you've tried
3. Include error messages and logs
4. Provide environment details

### Reporting Issues

Use our issue templates:
- [Bug Report](ISSUE_TEMPLATE/bug_report.md)
- [Feature Request](ISSUE_TEMPLATE/feature_request.md)
- [Documentation](ISSUE_TEMPLATE/documentation.md)

---

## Recognition

Contributors are recognized in:
- GitHub contributors list
- Release notes (for significant contributions)

Thank you for contributing to Django Ninja Boilerplate!

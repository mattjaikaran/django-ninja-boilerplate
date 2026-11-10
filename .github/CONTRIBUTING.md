# Contributing to Django Ninja Boilerplate

Thank you for your interest in contributing to Django Ninja Boilerplate! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Making Changes](#making-changes)
- [Work Flow](#work-flow)
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

- **Python 3.13+** - [Download Python](https://www.python.org/downloads/)
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
just setup

# Check your environment
just doctor
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
   uv sync --extra dev
   ```

3. **Set up environment variables:**

   ```bash
   just setup-env   # .env with generated secrets (docs/ENV_SECRETS.md)
   ```

4. **Start required services:**

   ```bash
   docker compose --profile test up -d db valkey
   ```

   (The `test` profile publishes just Postgres and Valkey. Use `just dev` for
   the full development stack.)

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
   just test
   just lint
   ```

### Running the Development Server

```bash
# Start with Docker (recommended)
just up

# Or run locally
just legacy local-run

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
just lint      # Check linting
just format    # Auto-format code
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

### Python and Django Ninja standards

`AGENTS.md` section 08 is the single source: it lists the hard bans and links
the full rules in
[`code-rules.md`](../.agents/skills/django-ninja-dev/references/code-rules.md).
Worked examples are in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) and
`.context/EXAMPLES.md`; wrong vs. right code in
[`django-ninja-anti-patterns.md`](../.omp/rules/django-ninja-anti-patterns.md).
`just gauntlet-quick` enforces most of it; the rest is review.

## Making Changes

### Branch Naming

Use a type prefix and a short description:

```
feature/add-user-authentication
fix/resolve-token-expiration-bug
refactor/simplify-database-queries
docs/update-api-reference
test/add-integration-tests
chore/update-dependencies
```

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

## Work Flow

Read [docs/product/journeys.md](../docs/product/journeys.md) before you pick
up work. It holds the personas, user stories, journeys, backend surface and
delivery waves.

1. Pick an issue. Each issue names one wave and one size.
2. Work the waves in order: W1 backend, W2 frontend, W3 Playwright, W4
   optional apps and scale. Do not start W2 for a journey whose backend smoke
   test is missing or failing.
3. Branch from `main`: `feature/`, `fix/`, `refactor/`, `docs/`, `test/` or
   `chore/`. Overnight agents use `agent/<Spec ID>`.
4. Commit with `<type>(<scope>): <Capitalized imperative summary>`. Keep the
   subject at 50 characters or fewer and wrap the body at 72.
5. Open a PR with the template. Put `Closes #N` for every issue it closes.

### Sizes

| Size | Work | Who does it |
|------|------|-------------|
| S | Exact edits, no design choice, about 300 changed lines or fewer | Overnight agent (small model, for example Haiku or DeepSeek Flash) |
| M | Fixed design, several files, about 300 changed lines or fewer | Overnight agent (small model, for example Haiku or DeepSeek Flash) |
| L | Open design, a new service or a cross-cutting refactor | Supervised session with a frontier model, which splits it into S and M specs |

A frontier model splits an L issue into S and M specs before any executor
starts. An executor never takes an L issue.

### Batch PRs

Do not open a PR for each small issue. Group similar issues in the same area
and wave into one batch PR:

- One area per PR: backend, frontend, data or infra.
- 2,000 changed lines or fewer, excluding lockfiles and generated files.
- One commit per issue, so a reviewer can read the batch issue by issue.
- The PR closes every issue in the batch.

### Overnight agents (agent-run)

Unattended work travels as specs in `tasks/specs/S-*.md`. agent-run claims a
spec whose `Status` is `READY`, runs the coding agent, opens the PR, and asks
matt-reviewer to review it. See [tasks/specs/README.md](../tasks/specs/README.md)
for the format and [docs/AGENT_HANDOFF.md](../docs/AGENT_HANDOFF.md) for the
roles, review order and the canonical delivery path.

The repo also ships a self-hosted ticket worker (`scripts/worker_once.py`
with `docs/tickets/`). It is a fallback for machines that do not run
agent-run. Do not run both queues on the same repository at the same time.

## Pull Request Process

### Before Submitting

1. **Sync your branch:**

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks:**

   ```bash
   just lint              # Linting passes
   just test              # Tests pass
   just format            # Code is formatted
   just gauntlet-quick    # Full quality gate (recommended)
   just check-journeys    # Features, journeys and Playwright tags agree
   just openapi           # After a schema or route change; commit the file
   ```

3. **Update documentation** if needed

4. **Add tests** only where the testing policy below requires them

### Submitting a PR

1. Push your branch to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request on GitHub

3. Fill out the PR template completely

4. Request review from maintainers

### PR Review Process

The factory accounts already have access: `matt-assistant` opens PRs and
`matt-reviewer` reviews them. The order is fixed:

1. CI passes. `.github/workflows/ci.yml` runs lint, format, typecheck, tests,
   architecture, OpenAPI, migrations and the quick gauntlet in parallel. On a
   local clone the pre-push hook runs the quick gauntlet and the dependency
   audit; run `just gauntlet-quick` yourself.
2. `matt-reviewer` reviews the PR and posts the findings. Fix or answer each
   finding. A coding model cannot approve its own PR.
3. The owner (`mattjaikaran`) approves.

A PR merges only with both approvals on its current head commit. Rebase,
never merge `main` into the branch, so the approvals stay valid. Keep PRs
focused and within the batch size. Rebase merge when possible, else squash.

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
just test

# Run with coverage
just test-coverage

# Run specific test file
uv run pytest core/tests/test_user.py

# Run specific test
uv run pytest core/tests/test_user.py::test_name -v

# Run with print output
uv run pytest -s
```

### Writing Tests

The testing policy in `AGENTS.md` section 10 is the single source: the three
layers, what earns a test, and what does not. A journey's backend smoke test
lives in `tests/smoke/test_jNNN_<name>.py` and calls the journey's endpoints in
order. Name an existing app test in
[`docs/product/journeys.md`](../docs/product/journeys.md) instead of copying
it.

See `todos/tests/` for examples.

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

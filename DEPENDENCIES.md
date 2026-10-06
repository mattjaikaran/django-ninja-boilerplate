# Dependencies

This file records dependency changes so they get reviewed instead of merging
silently. The `DEPENDENCIES` gauntlet gate fails when `pyproject.toml` changes
without a matching entry here.

## Tooling changes

- Removed the stale `api.pagination.offset` mypy override. Ninja Extra now
  provides pagination, and this module no longer exists. No package changed.
- Added `atlas` to the Hatch wheel package list. It is an installed app, so a
  built wheel without it failed `django.setup()`. No package changed.
- The Docker images (`Dockerfile`, `deploy/docker/Dockerfile.single`) now
  install the existing `observability` extra, so `OTEL_ENABLED=true` works
  without a rebuild. No new package; the extra was already locked.
- Removed `python-jose`. No code imports it; JWTs use `PyJWT` through
  `django-ninja-jwt`. It pulled in `ecdsa`, which has an advisory with no
  fixed version (PYSEC-2026-1325), plus `rsa` and `pyasn1`.
- Lockfile upgrades to clear `pip-audit` advisories, with no range change in
  `pyproject.toml`: `pip` 26.2.1 (`dev`, through `pip-audit`); `flask` 3.1.3,
  `werkzeug` 3.1.9, `python-engineio` 4.14.0, and `python-socketio` 5.17.0
  (`testing`, through `locust`); and `strawberry-graphql` 0.327.7
  (`graphql`). `mcp` stays at 1.27.2 because `django-ai-boost` requires
  `fastmcp<4`; it is used in the `dev` extra only.
- Pre-commit hooks are all `repo: local`. ruff, mypy and commitizen run from
  the `dev` extra through `uv run`, so the hook deps `django-stubs`,
  `djangorestframework-stubs` (DRF is banned), `types-requests` and
  `types-python-dateutil` are gone from `.pre-commit-config.yaml`. Tools
  outside the lock run pinned through `uvx` (`pre-commit-hooks` 5.0.0,
  `djhtml` 3.0.7, `hadolint-py` 2.14.0.1, `shellcheck-py` 0.10.0.1) or `bunx`
  (`prettier` 3.9.9). No project dependency changed.
- `just security-full` runs `semgrep` 1.179.0, `cyclonedx-bom` 7.5.0 (through
  `uvx`) and `aquasec/trivy:0.75.0` (through Docker). They are not project
  dependencies.

## Policy

- Base dependencies install for everyone.
- Situational packages go in an optional extra under
  `[project.optional-dependencies]` and fail loud when absent.

## Supported Django versions

`Django>=5.2,<6`. **5.2 LTS** is the only supported version. Django 6 is
tracked, not supported: run it by hand with `just test-django6`, which layers
Django 6.0 over the project environment with `uv run --with` (the main `.venv`
keeps 5.2) and runs the suite. It is not a gauntlet gate.

### Django 6.0: blocked on declared support

Measured 2026-10-05 with `just test-django6`: Django 6.0.8 with the locked
versions below passed the whole suite (229 tests) on SQLite and on PostgreSQL.
No package forbids 6.0 in its requirements. The blockers are packages that do
not declare 6.0 support, so a 6.0 break in them is not a bug they promise to
fix.

Checked against PyPI metadata (`Requires-Dist` and `Framework :: Django ::`
classifiers) on 2026-10-05:

| Package | Locked | Latest | Declared Django versions (latest) | 6.0 status |
|---|---|---|---|---|
| `django-ninja-jwt` | 5.4.4 | 5.4.5 | up to 4.1 | Blocker: no 5.x or 6.x classifier |
| `django-csp` | 4.0 | 4.0 | up to 5.2 | Blocker |
| `django-import-export` | 4.3.9 | 4.4.1 | up to 5.2 | Blocker (no 5.x release exists) |
| `django-storages` | 1.14.6 | 1.14.6 | up to 5.1 | Blocker |
| `django-ninja-extra` | 0.31.4 | 0.31.7 | 6.0 | Clears with a lock upgrade (0.31.4 declares up to 5.0) |
| `django-unfold` | 0.66.0 | 0.108.0 | 5.2, 6.0, 6.1 | Clears with a lock upgrade (0.66.0 has no classifiers) |
| `django-vcache` | 2.3.0 | 3.2.0 | 6.0 (2.3.0 too) | Not a blocker; see the macOS cap under Known constraints |

Revisit when the four blockers declare 6.0. Then upgrade the lock, widen the pin
to `<7`, and run `just test-django6` on SQLite and PostgreSQL
(`CI=1` selects PostgreSQL in `api.settings.test`).

### Django 6.1: blocked on install constraints

Two locked packages forbid 6.1, so it does not resolve:

- `django-celery-beat` 2.9.0 (the newest release) requires `Django<6.1`.
  `CELERY_BEAT_SCHEDULER` names its database scheduler and Celery is the
  default task backend, so the package cannot become optional.
- `django-ninja` 1.6.2 requires `Django<6.1`. 1.7.1 lifts this and declares 6.1.

## Supported Python versions

**3.13** in the Docker images, `requires-python`, and the tool targets;
`scripts/check_version_drift.py` keeps them equal. **3.14 is excluded** because
`pydantic-core` 2.33.2 publishes no cp314 wheels, so the install builds it from
source and fails without a Rust toolchain. Add 3.14 once pydantic-core ships
cp314 wheels.

## Base dependencies

| Package | Version | Why |
|---|---|---|
| `whitenoise` | `>=6.9` | Serves `/static/` from Gunicorn in the `single` and PaaS image, which has no nginx. Without it the admin and `/api/docs` assets returned 404 there. The `prod` profile's nginx still serves static files first. |
| `psycopg[binary,pool]` | `>=3.2.0` | Replaces `psycopg2-binary`. Django 5.2 pools connections only with psycopg 3 (`OPTIONS["pool"]` is ignored with psycopg2). The binary wheel bundles libpq, so the images no longer install `libpq5`/`libpq-dev`. |
| `uvicorn-worker` | `>=0.4.0` | Gunicorn worker class that serves `api.asgi:application` through uvicorn. Production moved from WSGI `gthread` to ASGI. Pulls `uvicorn`. |
| `celery` | `>=5.6.1` (was `>=5.5.2`) | 5.6.1 closes Django connection pools in prefork children. The lock was already on 5.6.2. |

## Known constraints

- `django-vcache` publishes **manylinux wheels only**. On Linux (CI, Docker)
  3.x installs from a wheel; on macOS/Apple Silicon there is no wheel, and
  3.2.0 fails to compile (`no method named set_user_timeout`). A blanket
  `uv lock --upgrade` therefore breaks on macOS. `pyproject.toml` caps it at
  `<3.2.0` and the lockfile stays on the known-good 2.3.0; widen the cap after
  testing 3.x on macOS.
- Every local installed app, including `atlas`, is in the wheel package list,
  so installs from a built wheel can run `django.setup()`.
  `core/tests/test_packaging.py` checks it.
- `mcp` is held below 2.0 by `django-ai-boost`'s `fastmcp<4` requirement
  (fastmcp 3 needs `mcp<2`). The `ai` extra pins `mcp>=1.28.1,<2` so both
  extras resolve together; the app MCP server uses the 1.x `FastMCP` API.

## Optional extras

### `ai`

Opt-in AI and data layer (`docs/AI_LAYER.md`). The LLM client uses `httpx`
(a base dependency) against the OpenAI-compatible API, so there is no LLM SDK.
LiteLLM was rejected: a large dependency tree, and the March 2026 malicious
PyPI releases (GHSA-5mg7-485q-xm76).

| Package | Version | Why |
|---|---|---|
| `pgvector` | `>=0.5.0` | `VectorField`, `HnswIndex`, `CosineDistance` and the `VectorExtension` migration operation for `core.ai`. 0.5.0 returns vectors as lists and drops NumPy. |
| `mcp` | `>=1.28.1,<2` | App-level read-only MCP server (`core/mcp/server.py`). `<2`: see Known constraints. |

### `dev`

| Package | Version | Why |
|---|---|---|
| `django-ai-boost` | `>=0.9.0` | Backs the dev-profile `mcp` compose service, started by `scripts/run_dev_mcp.py` (SSE on port 8001, bearer token required). Pulls `fastmcp`. |

### `dramatiq`

| Package | Version | Why |
|---|---|---|
| `dramatiq[redis]` | `>=1.17.0` | Fifth task backend. The Redis extra lets its worker use the existing Valkey service. The task facade fails loud when the extra is absent. |

### `observability`

| Package | Version | Why |
|---|---|---|
| `opentelemetry-instrumentation-psycopg` | `>=0.41b0` | Replaces `opentelemetry-instrumentation-psycopg2`, which cannot trace psycopg 3 connections. |

### `sentry`

| Package | Version | Why |
|---|---|---|
| `sentry-sdk[django]` | `>=2.71.0,<3` | Optional Sentry or GlitchTip reporting with PII scrubbing (`core/observability/sentry.py`). `<3`: a proposed breaking change (getsentry/sentry-python#7772) removes `EventScrubber` and the `event_scrubber` option, which the scrubbing depends on. |

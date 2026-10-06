# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Upgrading a platform from 1.12.0? Follow [UPGRADING.md](UPGRADING.md): several
changes refuse to start the app until you set new configuration.

This release supersedes the cookie-only auth change in commit `619422e`
("switch application auth to cookies"). Browsers authenticate with httpOnly
cookies and CSRF as described in `docs/COOKIE_AUTH.md`, and the bearer routes
`/api/token/pair`, `/api/token/refresh` and `/api/token/verify` stay, now
throttled. Local frontend origins on ports 3000 and 5173 are trusted in
development.

### Added
- **Generated `.env` secrets** (`scripts/env_secrets.py`, `docs/ENV_SECRETS.md`): `dnm init`, `dnm setup`, `just setup-env`, `scripts/setup.sh` and `scripts/quickstart.sh` write `.env` with mode 0600 and generate `SECRET_KEY`, a distinct `NINJA_JWT_SIGNING_KEY`, the Centrifugo token secret, API key and admin password/secret, `DJANGO_MCP_AUTH_TOKEN`, and the DB, Valkey, Flower, Neo4j and superuser passwords. They never replace an existing `.env`, never print a value, and add `.env` to `.gitignore` when no entry covers it. `just setup-env` on an existing `.env`, `just setup-services` and `generate_secret_key.sh --update-env` fill only missing, empty or placeholder values, and keep a placeholder `DB_PASSWORD` or `NEO4J_PASSWORD` because the data volume stores it; `scripts/doctor.sh` names weak secrets. `scripts/generate_realtime_secret.sh` is removed. `quickstart.sh` no longer writes or prints the `admin123` superuser password, and `setup.sh --auto` no longer prints `SUPERUSER_PASSWORD`. A `dnm init` monorepo's root `.env` reuses the backend's generated `DB_PASSWORD`.
- **`TASK_BACKEND=none`**: runs no task worker. Direct task calls still run in process; `.delay()` and retry dispatch raise `TaskDispatchDisabled` instead of queueing a job that nothing consumes. `just dev` starts only the `dev` profile in this mode.
- **DRIFT gate** (`scripts/check_version_drift.py`, `just check-drift`, in `gauntlet-quick`): fails when the Python, uv, Postgres or Valkey version differs between `pyproject.toml`, Dockerfiles and Compose, when uv is installed unpinned, or when a pre-commit hook runs a locked tool outside `uv.lock`.
- **Blocking dependency audit** (`just audit`, `scripts/audit_dependencies.py`): `pip-audit` on every package in `uv.lock`. Known advisories go in `pip-audit-allowlist.toml` with a reason and an expiry date; an expired entry fails.
- `just security-full`: optional bandit, audit, semgrep (pinned `semgrep-rules` commit), CycloneDX SBOM (`build/sbom.cdx.json`) and trivy image scan.
- `just test-django6`: manual Django 6.0 run through `uv run --with`, so `.venv` keeps Django 5.2. Django 6 is not supported yet; `DEPENDENCIES.md` lists the blockers.
- The gauntlet runs the `cli/` tests (CLI-TEST, also in `gauntlet-quick`); the full gauntlet also builds the production image (DOCKER, skipped without Docker). The pre-push hook runs `just gauntlet-quick`.
- "Testing policy" in `AGENTS.md` and two TTSR rules in `.omp/rules/`: one interrupts when an agent writes a test file, one asks the judge model to flag tests that assert only on mocks or existence.
- **Cookie auth for browser frontends** (`docs/COOKIE_AUTH.md`): logins also set httpOnly, `SameSite=Lax` `access_token` and `refresh_token` cookies (`Secure` when `USE_TLS`). New `GET /api/auth/csrf` sets the readable `csrftoken` cookie and returns `{"csrfToken"}`; new `POST /api/auth/refresh` rotates the cookies and blacklists the old refresh token. `ApiCsrfMiddleware` replaces `CsrfViewMiddleware` and requires `X-CSRFToken` on every unsafe `/api/` request, including login and refresh; failures return 403 with code `csrf_failed`. Requests with only an `Authorization` or `X-API-Key` header and no auth cookie skip CSRF, so bearer clients keep working; `/api/token/*` stays CSRF-exempt. The SSE stream accepts the access cookie.
- **Committed OpenAPI contract**: `docs/openapi/openapi.json` with sorted keys and stable operationIds. `just openapi` regenerates it; `just openapi-check` and the OPENAPI and SCHEMA-PARITY gates (in `gauntlet-quick`) fail when it is stale or has snake_case, untyped, or inconsistent required/nullable properties (`scripts/check_schema_parity.py`). The `SCHEMA_ANY` convention check requires `# schema-ok: <reason>` on `Any`, bare `dict`, or `Json` schema fields.
- Explicit `Field` constraints, `Literal` choices, and typed nested schemas across the public schemas, so OpenAPI and generated Zod carry them.
- **Opt-in AI and data layer** (`ai` extra, `docs/AI_LAYER.md`). `AI_ENABLED=true` installs `core.ai`: a migration that creates the `vector` extension, and an example `Document` model with a 1536-dimension `VectorField` (HNSW, cosine), a generated `tsvector` (GIN), and a `DocumentLink` edge model. `AIClient` calls any OpenAI-compatible API over httpx (OpenAI, Ollama, vLLM, OpenRouter, a LiteLLM proxy), emits OpenTelemetry GenAI spans, and caches chat responses in Valkey under a SHA-256 of model, messages and parameters for `AI_CACHE_TTL` seconds. `embed_document` runs through `api.tasks`. `hybrid_search` fuses Postgres full-text rank and pgvector cosine distance with reciprocal rank fusion; `reachable` walks an edge table with a recursive CTE (the default graph option).
- `POSTGRES_IMAGE` selects the Postgres image of `db`, `db-prod` and `db-single` (default unchanged, `postgres:17-alpine`); set `pgvector/pgvector:pg17` for the AI layer. New Compose profiles: `ai` (Qdrant 1.19.2) and `graph` (Neo4j 5.26 LTS community).
- **App-level read-only MCP server** at `/api/mcp` (`MCP_ENABLED=true`, ASGI only, `core/mcp/server.py`). Exposes the GET routes listed in `MCP_TOOLS` as tools, requires a JWT access token (401 without one), and replays each call through Django with the caller's token. Separate from the dev-only `mcp` profile.
- **Sentry or GlitchTip** (`sentry` extra): `SENTRY_DSN` starts the SDK with `send_default_pii=False`, no local variables, and a recursive scrubber for auth cookies, tokens, API keys, email and OTP codes.
- `UV_EXTRAS` build arg (space-separated extra names) in both Dockerfiles, passed through every Compose build and `just trivy`. `UV_EXTRAS="sentry" just prod-build` bakes the `sentry` extra into the images.

### Changed
- **Django pin narrowed to `Django>=5.2,<6`.** 6.0 is no longer a supported install; `DEPENDENCIES.md` lists the packages that do not declare 6.0 support.
- **No hosted CI.** `.github/workflows/ci.yml` is removed; its lint, test, CLI test, audit and Docker build steps run in `just gauntlet`.
- Every pre-commit hook is `repo: local`: ruff, mypy and commitizen run through `uv run`, other tools through a pinned `uvx` or `bunx`. This drops the drifted `mirrors-mypy` 1.14.0 and bandit 1.8.0 hooks and the `djangorestframework-stubs` hook dependency. `just pre-commit-install` installs the pre-commit, commit-msg and pre-push hooks.
- `just test` runs only the tests for files changed since HEAD, without coverage, and stops at the first failure. `just test-all` runs every test without coverage; coverage runs in `just gauntlet`.
- The AUDIT gate blocks in every mode, including `--ci`.
- **Responses serialise by alias (camelCase) everywhere.** Endpoints that returned a dict (for example `/api/auth/status` `user_id`) used to emit snake_case and the OpenAPI responses documented snake_case; both now use the `CamelCaseSchema` aliases (`userId`).
- `/api/auth/login`, `/api/auth/login/username` and `/api/auth/passwordless/login/verify` declare typed responses. `POST /api/auth/logout` takes the refresh token from the body or the cookie, so the body is optional, and it clears the auth cookies.
- CORS and CSRF origins default to `FRONTEND_URL` in every environment (`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` env overrides). Production no longer sets `CSRF_COOKIE_HTTPONLY=True`, which hid the token from the client. `USE_TLS` moved to `common.py`.
- nginx proxies only `/api/` and `/admin/` to Django, serves `/static/` and `/media/`, and returns 404 for everything else. It has an unbuffered SSE location and no longer sends a second Content-Security-Policy header. The monorepo generator emits `bun` instead of `npm` targets.
- **Production serves ASGI.** Gunicorn runs `api.asgi:application` with `uvicorn_worker.UvicornWorker`. `gunicorn.conf.py` holds the settings (`GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, `PORT`), so the Dockerfile, Compose `django-prod`, `Dockerfile.single`, Railway and k3s run the same `gunicorn api.asgi:application`. Image health checks probe `$PORT`.
- **psycopg 3 with Django's connection pool.** `psycopg[binary,pool]` replaces `psycopg2-binary`, and `opentelemetry-instrumentation-psycopg` replaces the psycopg2 instrumentation (`instrument_all()` key `psycopg`). `CONN_MAX_AGE` is `0` everywhere (it was 600, and 60 in prod) and `CONN_HEALTH_CHECKS` is on. `DB_POOL_ENABLED`, `DB_POOL_MIN_SIZE` (2), `DB_POOL_MAX_SIZE` (10) and `DB_POOL_TIMEOUT` (10 s) size the per-process pool; task worker services set `DB_POOL_ENABLED=false`. Sizing rules are in `docs/ARCHITECTURE.md`. Celery minimum is 5.6.1.
- Docker images copy a pinned uv (`ghcr.io/astral-sh/uv:0.12.1`) instead of running the curl installer, drop `libpq5`/`libpq-dev`, and set `org.opencontainers.image.version` from the `VERSION` file (the justfile exports `APP_VERSION`; Compose passes it as a build arg).
- Docker images pin Python with `ARG PYTHON_VERSION=3.13.15` and `ARG PYTHON_IMAGE_DIGEST` (`python:3.13.15-slim-trixie@sha256:…`) for every stage, run `apt-get upgrade`, and remove the base image's pip. The DRIFT gate fails on a floating `FROM python:` tag or when the two Dockerfiles disagree on version or digest.
- The `single` profile cache runs `valkey/valkey:8-alpine` instead of `redis:7.2-alpine`.
- License is MIT in `pyproject.toml` (was `Proprietary`), matching the README badge and `cli/`. A `LICENSE` file is added.
- Production images install the project with `uv sync --locked --no-dev --no-editable` instead of an editable `uv pip install -e .`.

### Fixed
- Return 401, not 500, for a malformed, expired or revoked refresh cookie.
- Export stable operationIds without ninja-extra's random suffix, so the generated frontend contract is deterministic.
- Exempt only the public health, liveness, and readiness routes from TLS redirects. Keep Host validation and redirects for admin and staff detail routes.
- `SENTRY_DSN` set without `sentry-sdk` installed crashed startup with `ImproperlyConfigured`. It now logs an error and the app runs without error reporting.
- `billing`: `Plan.stripe_price_id` and `Subscription.stripe_subscription_id` were `unique=True` with an empty default, so a second free plan or a second incomplete subscription raised `IntegrityError`. Uniqueness now applies only to non-empty values (migration `0003`).
- Password reset logs the user id instead of the email address.
- `scripts/openapi/export_insomnia.py` generated resource ids from an MD5 of `time.time()` and `id(object())`, which can repeat within one export. It now uses `secrets.token_hex`.
- `dnm` clone passes `--` before the repository URL, so a URL that starts with `-` cannot become a git option.
- semgrep false positives (JSONFields with a default, imports from `INSTALLED_APPS`, argument-list `subprocess` calls) carry a narrow `# nosemgrep: <rule>` with a reason. `just semgrep` reports 0 findings.
- Install the locked development tools when you run quality and gauntlet recipes from a fresh clone.
- `scripts/check_cross_stack.py` crashed with `ValueError` in a monorepo when it reported a frontend path, because `frontend/` is not inside the backend root. It now reports sibling paths as `../frontend/...`. It also skips `.venv`, `node_modules`, and caches, so installed packages no longer appear as backend models and schemas.
- Report nonblocking findings as warnings, not passed gates. JSON distinguishes `all_passed`, `blocking_passed`, and `has_warnings`; warning-only runs keep their documented zero exit without claiming an all-clear.
- Audit the actual project environment in the standalone pre-push hook, without advisory ignores. Update locked MCP and virtualenv dependencies to patched releases.
- Isolate test JWT signing from local environment keys, remove source hook whitespace failures, and report development deployment-check findings as nonblocking warnings.
- Under ASGI the SSE stream (`/api/events/stream/`) sent nothing: Django drains a sync iterator with `list()`, and GZip split async chunks into separate gzip members. The view now streams `sse_stream_async` under ASGI, keeps the sync generator under WSGI, and is not gzipped.
- SSE streaming and `broadcast_event` raised `ValueError` on the shipped `valkey://` `REDIS_URL`, because redis-py accepts only `redis://`, `rediss://` and `unix://`. They now rewrite the scheme the way the health check does.
- The cache readiness probe used one shared key, so concurrent probes deleted each other's value and returned 503 "read/write mismatch". Each probe now uses its own key.

### Removed
- `test_prod_django_behind_nginx_trusts_one_proxy` read `docker-compose.yml` as text instead of testing behaviour. The trusted-proxy behaviour tests in `core/tests/test_throttling.py` remain.
- Twelve tests in `tests/smoke/` that copied app tests (health, signup, refresh, `/auth/me`, todo CRUD) or pinned defaults (development HSTS and CSP, the test settings import), and one assertion on error-message wording.
- `Dockerfile.uv`: it copied Python 3.13 packages into a 3.14 image and was referenced by no build. Use `Dockerfile`.
- `SECURE_BROWSER_XSS_FILTER`: Django 4.0 removed the `X-XSS-Protection` header it controlled.

### Security
- `nginx/nginx.conf` proxied every `/centrifugo/` path, so the Centrifugo server API was public and any holder of the committed key could publish, disconnect users and read presence on every channel. nginx now proxies only `/centrifugo/connection/websocket`; every other path returns 404.
- `deploy/centrifugo/config.json` no longer holds `api_key`, `admin_password`, `admin_secret` or `token_hmac_secret_key`; the admin UI is off by default. Centrifugo treats an empty environment variable as unset and falls back to the config file, so the committed key applied whenever `CENTRIFUGO_API_KEY` was empty. `centrifugo-prod` now requires `CENTRIFUGO_API_KEY` (`:?`), and `api/settings/prod.py` refuses the committed Centrifugo keys. The dev `centrifugo` service enables the admin UI on loopback only.
- `SUPERUSER_PASSWORD` is empty in `.env.example`, `.env.development` and the settings default (it was `Password123!`, so `manage.py create_superuser` created that admin when the variable was unset). Outside `ENVIRONMENT=development`, both `docker-entrypoint.sh` and `create_superuser` refuse published default passwords and passwords shorter than 12 characters. The unused `FLOWER_USER`/`FLOWER_PASSWORD` template values are gone. Dev Centrifugo, Flower and Neo4j ports stay pinned to `127.0.0.1` instead of following `DEV_BIND_ADDRESS`.
- `docker-compose.yml` no longer falls back to published secrets: `DB_PASSWORD` (`postgres`), the dev Centrifugo token secret, API key and admin password/secret, `FLOWER_BASIC_AUTH` (`admin:password`) and `NEO4J_PASSWORD` (`devpassword`) use `${VAR:?...}` guards. Compose interpolates every service, so run `just setup-env` before any `docker compose` command; on an existing `.env` it now generates only the missing secrets. `scripts/check_env_secrets.py` (in the test suite) fails when a secret that Compose, `deploy/`, `api/settings/prod.py` or `docker-entrypoint.sh` requires is missing from `scripts/env_secrets.py`, or when Compose falls back to a published value for a secret. `dnm init` and `dnm setup` exit 1 when the project has no `scripts/env_secrets.py`, and `dnm init` exits 1 when a generator step fails. `env_secrets.py list --json` and `create --env-file/--no-template/--only/--exclude` give mattstack a stable interface (`docs/ENV_SECRETS.md`).
- `.claude/` is ignored: a committed `settings.local.json` once exposed a local absolute path.
- `/api/tasks/*` (status, progress, recent, active, stats, revoke, cleanup) required only a JWT, so any signed-up user could read every task's result and error, revoke or terminate any task, and delete all results. The controller now requires a staff user, like the scheduler and dead-letter routes, and `cleanup` rejects `days` below 1 (a negative value deleted every row).
- Staff users could update or delete superusers through `PUT`/`DELETE /api/users/{user_id}`, although only superusers may create them. Both now return 403 unless the caller is a superuser.
- `/api/token/pair`, `/refresh` and `/verify` had no throttle, so they allowed unlimited password guessing beside the throttled `/api/auth/login`. They now use the `anon-auth` rate.
- OTP: every `/api/auth/otp/` route uses the `anon-auth` throttle. The per-identifier request limit lower-cases the email, so case variants no longer each get a fresh budget. Codes come from `secrets`, attempts are counted atomically in the database, and a code can be used once even under concurrent requests. Request and verify return the same message whether or not the account exists. The SMS and push placeholders no longer log the code, which the client-chosen delivery method could route into the logs.
- `nginx/nginx.conf`: `/media/` responses send `X-Content-Type-Options: nosniff` and a sandboxing `Content-Security-Policy`, so an uploaded HTML or SVG file cannot run script on the API and admin origin.
- Dev `mcp` profile: django-ai-boost served settings (including `SECRET_KEY`) and model rows over SSE with no authentication. `scripts/run_dev_mcp.py` now requires `DJANGO_MCP_AUTH_TOKEN` (32+ characters) as a bearer token, refuses to start unless the settings are `api.settings.dev` with `DEBUG` on, and rejects Host headers other than `localhost` and `127.0.0.1` (DNS rebinding). The service joins only a new `mcp-network` (with `db` and `valkey`), its host port stays `127.0.0.1:8001`, and `just up-mcp`, `just up-full` and `just mcp` stop early without a token. `docs/AI_LAYER.md` documents the residual risk and prefers the stdio transport.
- Refresh tokens: a rotated (blacklisted) refresh token presented again to `/api/auth/refresh` or `/api/token/refresh` more than 30 seconds after its rotation now returns 401 and revokes every outstanding refresh token of the user (`core/security/refresh_tokens.py`). Inside the 30-second grace window (two tabs, React StrictMode, a retried fetch) the repeat only gets 401, so concurrent refreshes no longer log the user out everywhere. Rotation now records each new refresh token as outstanding, so revocation reaches it. Every password change (OTP reset, admin form, `changepassword`, any `set_password()` + `save()`) revokes all refresh tokens of the user. `POST /api/auth/logout` no longer needs an access token, so it revokes the refresh token and clears the cookies after the access cookie has expired.
- Production requires TLS: `api.settings.prod` refuses to start with `USE_TLS=false`, because cookie auth needs HTTPS outside localhost (browsers drop `Secure` cookies on plain HTTP, and cookies without `Secure` travel in clear text). The bundled nginx now passes the outer TLS proxy's `X-Forwarded-Proto` through instead of overwriting it with `http`, so `USE_TLS=true` works behind it; `.env.deploy.example`, the prod Compose services and the single image default to `USE_TLS=true`. `ALLOW_INSECURE_COOKIES=true` allows a local plain-HTTP smoke run with the prod settings and is rejected when `ENVIRONMENT=production`.
- Account enumeration: `POST /api/auth/signup` now always returns `202` with `{"message": "Check your email to finish signing up."}` and sends one email (welcome, "account exists" notice, or "username taken"), instead of `201` with the user or `400` for a taken email or username. It uses the `anon-email` throttle. Magic-link and OTP emails go out on a background thread, so timing does not reveal accounts. Username login hashes the password for unknown usernames. The OTP `SIGNUP_VERIFICATION` request no longer answers "Email already registered".
- Login lockout: password logins (`/api/auth/login`, `/api/auth/login/username`, `/api/token/pair`, admin form) share one per-account counter (a known username counts against its email) and lock an (account, client IP) pair after 5 failures and a client IP after 20, for 15 minutes. Locked requests get 429 even with the right password. The lock never covers an account for every source, so an attacker cannot lock the owner out.
- `ADMIN_URL` (default `admin/`) sets the admin mount path, including the atlas and observability pages. Update the nginx `location` regex when you change it.
- AI `Document` has a required `owner` (in `ai.0001_initial`; the app is new in this release). `hybrid_search` and `reachable` need `user` and return only that user's documents.
- `API_DOCS` (`public`, `staff`, `off`) controls `/api/docs` and `/api/openapi.json`. Production defaults to `off`.
- Client IP: `get_client_ip` (audit log, OTP, observability) used the leftmost `X-Forwarded-For` entry, which the client controls. It now trusts only `NINJA_NUM_PROXIES` proxies, like the throttles, and uses `REMOTE_ADDR` by default. The Compose `prod` profile now defaults to `NINJA_NUM_PROXIES=2` (TLS proxy plus nginx) and the single image to `1`; with the old default of 1 behind the required TLS proxy, every client shared the proxy's IP and one IP lockout applied to the whole site.
- `API_CSRF_EXEMPT_PATHS` includes `/api/billing/webhooks/`: once billing was enabled, `ApiCsrfMiddleware` returned 403 to every Stripe webhook. The receiver verifies the Stripe signature.
- The files and webhooks apps sit behind `FILES_ENABLED` and `WEBHOOKS_ENABLED`, both off by default. Webhook URLs and deliveries are protected from SSRF: https only, public addresses only, connection pinned to the checked IP, no redirects, short timeouts, capped reply size. File uploads are checked for size, allowed type and matching file signature, and use owner-scoped random storage keys.
- The staff-route 403 table in `core/tests/test_route_auth.py` now covers every staff-only route, and `FeatureFlagAdminController` requires a staff user.
- `DELETE /api/api-keys/{key_id}` and `POST /api/api-keys/{key_id}/rotate` returned 500 for a missing key or another user's key. They now return 404.
- Sentry: with `SENTRY_DSN` set and `sentry-sdk` missing, startup now fails (`ImproperlyConfigured`) in every `ENVIRONMENT` except `development`, which still only logs an error.
- Tests: `billing/tests` and `tests/contract` run in the default suite (the test settings install the billing models; `billing/tests/urls.py` mounts its routes). The new `AI-DB` gauntlet gate (`just test-ai-db`) runs the Postgres-only tests (`core.ai` owner scoping, concurrent refresh) on a throwaway `pgvector/pgvector:pg17` container, fails if any of them skips, and prints a skip reason without Docker.

## [1.12.0] - 2026-09-29

### Added
- **Single profiled Compose file**: `docker-compose.prod.yml` and `docker-compose.single.yml` are gone; `docker-compose.yml` carries the application, task backend, production, realtime, monitoring, mail, and MCP profiles. The default development stack starts Django, Postgres, Valkey, and one task backend. Mailhog and MCP are opt-in.
- **justfile** — replaces the Makefile, which is kept as `Makefile.legacy`. Recipes cover dev, test, database, MCP, search, quality, gauntlet, production, and deploy.
- **Agent Skills** (`.agents/skills/`, `SKILLS.md`) — harness-agnostic skills: `django-ninja-dev`, `docker-compose-profiles`, `rtk-ripgrep`, `system-design-atlas`.
- **`AGENTS.md`** — hand-maintained agent guidance with a "Patterns We Do Not Use" section.
- **Uniform task contract**: `api.tasks.shared_task` now provides `.delay()` and `.retry()` across Celery, Huey, django-q2, django-rq, and the new Dramatiq backend. Each backend has a tested Compose worker profile.
- **CLI-driven setup**: `just setup` runs the in-repo `dnm` CLI, asks for the task backend, updates `.env`, and then builds the selected stack.
- **Refresh-token rotation**: `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION` are on. Access tokens last 60 minutes and refresh tokens 7 days. `POST /api/auth/logout` blacklists the refresh token. The `core.flush_expired_tokens` task (Celery beat) and the `flush_expired_tokens` command remove expired tokens. `NINJA_JWT_SIGNING_KEY` is separate from `SECRET_KEY`, and production requires it.
- **Scoped rate limits**: Ninja Extra throttles by scope: `anon-auth` and `anon-email` for anonymous auth endpoints, `user` for the authenticated API, and `tasks` for task admin. A throttled request gets 429 with `Retry-After` and `retry_after`. `NINJA_NUM_PROXIES` (default 0) sets the trusted proxy count for both Ninja and Ninja Extra.
- **Unified health probes**: one controller owns `/api/health`. Liveness and readiness are public; readiness checks only the database and cache and returns 503 on failure. Detailed, component, system, and metrics probes require a staff JWT.
- **Route access contract tests** (`tests/contract/`): every route is either on the public allowlist or requires auth, so a new public operation fails the suite.

### Changed
- **Breaking: list endpoints are paginated.** Every list endpoint returns the Ninja Extra `PageNumberPaginationExtra` envelope (`count`, `next`, `previous`, `results`) and declares `PaginatedResponseSchema[...]` in OpenAPI.
- **Breaking: routes require auth.** `/auth/me`, `/auth/status`, `/auth/logout`, and `/tasks` require a JWT. `/users`, `/audit`, the task scheduler, and the DLQ require staff; `POST /users/superuser` requires a superuser. Signup, login, and passwordless login stay public.
- **Exception handling is centralized.** Handlers registered on the shared API in `api/urls.py` map `BaseAPIException` to 400/401/403/404/409/429/502, Django `ValidationError` to 400, and any other exception to a JSON 500 without internal detail. Invalid login credentials return 400.
- The task backend set now includes Dramatiq through the `dramatiq` optional extra and Compose profile.
- `scripts/release.py`, `scripts/deploy.sh`, the `cli` monorepo generator, and `.env.deploy.example` follow the new Compose layout and `just` recipes.
- Docs (`README.md`, `.context/PROJECT.md`, `.context/PROMPTS.md`, `scripts/quickstart.sh`): stale `Makefile` references now name `justfile`; the old runner stays at `Makefile.legacy`.
- Docs now match the code where they disagreed: the README quick start, command list, and profile table; the deleted `docker-compose.yml (prod profile)` references in `docs/MIGRATION.md` and `docs/REALTIME.md`; the removed `django-csp` settings in `SECURITY_CHECKLIST.md`; the raw `ninja.Schema` examples in `.context/CONVENTIONS.md`, `.context/ANTI_PATTERNS.md`, `.context/PROJECT.md`, and `.context/SYSTEM_PROMPT.md` (the repo's own gate rejects raw `Schema`); the `uv sync --dev` instruction in `setup.md` and `README.md` (`dev` is an extra: `--extra dev`); and `ROADMAP.md`, whose banner still read v1.8.0.
- `.env.example` documents the compose-only host ports and tuning knobs it omitted: `POSTGRES_PORT`, `VALKEY_PORT`, `PORT`, `GUNICORN_WORKERS`, `CELERY_CONCURRENCY`, `OTEL_SERVICE_NAME`, `USE_STRUCTURED_LOGGING`, and the `TEST_*` integration ports.
- `docs/REALTIME.md` claimed Centrifugo expands environment variables in its config file. It does not; the guide now names the environment variables Centrifugo actually reads.
- `ROADMAP.md` gains a status column: 1.9.0 to 1.11.0 were proposal labels and the items under them remain unshipped, and the Django 6.0 item is marked done.
- The dev stack publishes Postgres on 5433 and Valkey on 6380 instead of 5432 and 6379 (`POSTGRES_PORT`, `VALKEY_PORT`). `doctor` warns that 5432 conflicts with a local Postgres, and the application only ever reaches these services over the compose network, so the host ports are free to be offset. `just test-integration` moves to 5434/6381 to stay clear of the dev stack. `doctor` now reads the configured ports instead of assuming the defaults.
- `docs/TASK_BACKENDS.md` and `.env.example` used the `valkey://` scheme for the Celery broker and result backend, which kombu cannot use.
- `scripts/check_conventions.py`: the `ROUTER_USAGE` rule no longer flags dotted third-party attributes.

### Removed
- The per-endpoint `@handle_exceptions` decorator. Use the centralized handlers.
- The inactive `api/versioning.py` and the `API_VERSIONING_ENABLED` v1/v2 mounts.
- The custom `rate_limit` decorator, `check_rate_limit`, and the `api.throttling` package. Use Ninja Extra throttles.
- The duplicate `api/pagination` package, the `core.schemas` pagination helpers, and the unused `core/schemas/users.py` schemas.
- The unused `python-jose` dependency.

### Fixed
- `nginx/nginx.conf`: `gzip_proxied` had an invalid `must-revalidate` token, so nginx aborted with `[emerg] invalid value` and the production reverse proxy never started. The `centrifugo` upstream also pointed at the pre-rename service name; it now resolves per request, so nginx starts even when the `realtime-prod` profile is not enabled.
- `docker-compose.yml` and `nginx/Dockerfile`: the `prod` nginx service published `443:443` and mounted `./nginx/certs`, but `nginx/nginx.conf` listens on port 80 only and that directory does not exist. TLS terminates at an external proxy (`USE_TLS` in `.env.deploy.example`), so the unused port mapping, the certs mount, and `EXPOSE 443` are gone.
- `scripts/doctor.sh`: `((PASS++))` returns the old value, which is `0` on the first call, and a `0` exit status aborts the script under `set -e`. Every counter used post-increment, so `doctor` never completed. Its connectivity check also probed a `redis` service that does not exist (the compose service is `valkey`).
- `scripts/deploy.sh`: the VPS path still referenced the pre-rename service names (`django`, `db`, `redis`). Quick deploy silently skipped migrations behind `2>/dev/null || true`, and the full deploy aborted at step 4. The health probe now uses port 80 (nginx), since `django-prod` is `expose:`-only.
- Shell scripts (`db_setup`, `doctor`, `quickstart`, `setup`, and `run_migrations.sh`) called `docker-compose` with no profile, which starts nothing now that every service belongs to a profile. `setup.sh` and `quickstart.sh` also generated an `.env` pointing at a `redis` host instead of the `valkey` service.
- `Dockerfile`: removed the silent fallbacks (`2>/dev/null || uv pip install -e .`, `collectstatic … || true`) that could produce a base-only image or skip static collection without reporting it.
- `.env.example`: dropped `COMPOSE_PROFILES`. Some Compose versions merge it with `--profile`, which would start the dev services during a production deploy.
- `docker-compose.yml`: task workers no longer share the `dev` profile. `TASK_BACKEND` selects exactly one worker profile, while Mailhog and MCP remain opt-in.
- `scripts/setup.sh` and `scripts/quickstart.sh`: readiness checks targeted the `redis` service, which exists only in the `single` profile, so `setup.sh` waited 30 seconds and then aborted on a healthy dev stack. Both now probe `valkey`.
- `deploy/docker/Dockerfile.single`: the image could not build. It put uv on the wrong `PATH` (`/root/.cargo/bin` instead of `/root/.local/bin`), resolved dependencies fresh instead of from `uv.lock`, targeted Python 3.14 (no `pydantic-core` wheels), and set neither `ENVIRONMENT=production` nor a migration step. It now mirrors the production stage: Python 3.13, `uv sync --locked`, `ENVIRONMENT=production`, and `migrate` before Gunicorn.
- `deploy/centrifugo/config.json`: the engine address named `redis`, a host that only exists in the `single` profile, so both Centrifugo services failed to start with `error creating engine: malformed connection address`. The address now uses a host that resolves in each profile (`CENTRIFUGO_REDIS_ADDRESS`), and `health: true` enables `/health`, so the container healthcheck passes instead of reporting `unhealthy` forever.
- Pre-commit: `shellcheck` and `hadolint` failed on the committed tree, so no commit could pass the hooks. Fixed the shellcheck findings across the shell scripts, fixed the Dockerfile warnings, and set hadolint to `--failure-threshold warning` so info-level hints stay non-blocking.
- `justfile`: `just setup` aborted on a fresh clone because nothing created `.env`; it now delegates environment creation and backend selection to the `dnm` CLI. `just legacy` is variadic, so it accepts documented target arguments.
- `docker-compose.yml`: no service read `.env`. Compose passes only what each service pins, so most of the documented settings (including `SUPERUSER_*`) never reached the containers. Application services now read `.env` through `env_file` (`required: false`), while the internal addresses stay pinned so a developer's `.env` cannot redirect them.
- `docker-compose.yml`: the `single` `app` service pinned `REDIS_URL` but not `VALKEY_URL`, which settings read first, and `.env` names a `valkey` service the single stack does not run. It also let `.env` override the image's `DJANGO_SETTINGS_MODULE` and `ENVIRONMENT`, so the PaaS image ran development settings. Both are pinned now.
- `docker-compose.yml`: `django-prod` and the production Celery services never pinned `CELERY_BROKER_URL`, so they fell back to the `valkey://` default. kombu has no valkey transport, so production workers could not connect. They now use the `redis://` scheme against `valkey-prod`.
- `deploy/centrifugo/config.json`: Centrifugo does not expand `${...}` in its config file, so `token_hmac_secret_key` stayed the literal placeholder while Django signed JWTs with the real secret. Every realtime connection token would have been rejected. Compose now sets `CENTRIFUGO_TOKEN_HMAC_SECRET_KEY` (the name Centrifugo maps onto that key), and the config holds development defaults only.
- `.env.example`: `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` used the `valkey://` scheme, which kombu cannot use outside Docker. They now use `redis://` against the Valkey service.
- `create_superuser`: running twice reported a failure. It now reports that the superuser exists and exits successfully.
- `justfile`: `just setup` is now a complete CLI-driven bootstrap. It creates `.env`, asks for the task backend, generates Django and Centrifugo secrets, runs `doctor`, builds and starts the stack, migrates, and creates the superuser. `just seed` loads sample data.
- `deploy/docker/Dockerfile.single`: the image used a `sh -c` command that migrated before the database was reachable. It now uses `docker-entrypoint.sh`, which waits for the database, migrates, creates the superuser when `SUPERUSER_*` is set, and collects static files. The runtime stage installs `netcat-openbsd` for that wait, and the main Dockerfile no longer copies an entrypoint no service referenced.
- CI: the test matrix ran Python 3.14, where `pydantic-core` has no wheels and the install builds from source and fails. The matrix is 3.13 with the reason recorded, and the test job now installs from `uv.lock` instead of resolving fresh.
- `scripts/release.py`: the release commit stages only the version files, so it now refuses to run on a dirty tree instead of silently leaving work out of the tagged commit.
- `api/settings/common.py`: `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` defaulted to `VALKEY_URL`, whose `valkey://` scheme kombu cannot use. Any path that did not set them explicitly (a bare settings import, a deployment that skipped the template) produced a broker that could not connect. The default now derives the `redis://` form.
- `docker-entrypoint.sh` created a superuser whenever `SUPERUSER_*` was set, so a deployment that reuses `.env.example` would provision an admin account with the published template password. It now requires `CREATE_SUPERUSER=true`.
- `scripts/generate_secret_key.sh` rotated `SECRET_KEY` on every run, which invalidated sessions and JWTs and overwrote a key taken from a secret store. It now writes only when the value is missing or is still the template placeholder. It also writes the value with Python instead of `sed` (a key containing `&` spliced the old line into the new value) and single-quotes it, because Compose interpolates `$` in `.env` values.
- `just setup` starts the stack with `--wait`. Task workers now depend on healthy Django, so migrations finish before any worker consumes jobs.
- Production services pin `USE_STRUCTURED_LOGGING=true`: `.env` carries the development value, which otherwise disabled JSON logging in production. `centrifugo-prod` requires `CENTRIFUGO_TOKEN_SECRET` instead of starting with an empty signing key, and `.env.deploy.example` documents the realtime variables.
- `.env.example` contradicted itself about host versus container values, and neither template mentioned the superuser opt-in.
- `docker-compose.yml`: the `mcp` service never stayed up. `uv run` tried to create `.venv` inside the read-only bind mount and exited, and the container inherited the image healthcheck for port 8000 while it serves 8001, so it reported unhealthy even when running. It now uses the image virtualenv and probes its own port. Both faults were invisible until `just setup` started using `--wait`.
- `core/tasks.py` collided with the existing `core/tasks/` package, so Django and Celery could not import four core jobs. The jobs now live in `core/tasks/jobs.py` with stable task names and package exports.
- Task definitions imported Celery directly, Huey exposed no `.delay()`, and missing optional packages silently fell back to Celery. All task definitions now use the backend-neutral facade and invalid configurations raise `ImproperlyConfigured`.
- Development workers could start before migrations, inherited the Django HTTP healthcheck, and caused `docker compose --wait` to fail. Workers now wait for healthy Django and disable the unrelated image healthcheck.
- `just setup` now generates a unique Centrifugo signing secret. Production settings reject the published development values.
- `dnm init --yes` no longer opens the project-type prompt. Non-interactive scaffolding now uses the standalone layout by default.
- `pyproject.toml`: the Hatch wheel omitted the installed `atlas` app, so `django.setup()` failed with `ModuleNotFoundError: No module named 'atlas'` from an installed wheel. A test now checks that every local installed app is packaged.
- `docker-compose.yml`: the production services required `NINJA_JWT_SIGNING_KEY` through a Compose `:?` guard. Compose interpolates every service, so an `.env` without the key also broke `just dev`. `api/settings/prod.py` still refuses to start without a distinct key.
- `just dev` and the other dev start recipes now run `up -d --build`. `just up-build` is gone because `just dev` does the same. `just build` now also builds the selected task worker.
- `docker-compose.yml`: the dev `django` container memory limit is now `DJANGO_DEV_MEMORY_LIMIT`, default `1G`, so you can raise the dev `django` container memory limit without editing the file.
- `scripts/quickstart.sh`: the Docker path started only the `dev` profile, hid `up` errors, and pointed at a `just up-celery` recipe that does not exist. It now runs `just dev`, which starts the worker named by `TASK_BACKEND`, and prints the log on failure.
- `scripts/release.py` ignored every `--` argument except `--dry-run`, so `--help` or a mistyped flag ran a real release that committed, tagged, and pushed. It now uses `argparse`: unknown flags exit with an error before any change, `--help` prints usage, and push is opt-in through `--push`. `just release` and `just release-dry-run` pass their arguments through.
- `docker-compose.yml`: `django-prod` never served traffic. Its folded `command:` kept each deeper-indented gunicorn flag on its own line, so `sh -c` ran `--bind`, `--workers`, and the rest as commands (`sh: 4: --bind: not found`). It also crashed at settings import because `EMAIL_PORT=${EMAIL_PORT}` pinned an empty string (`invalid literal for int()`); the email pins are gone and settings defaults apply.
- `docker-compose.yml`: `centrifugo-prod` exited with `NOAUTH` because its Redis address omitted `REDIS_PASSWORD`. It also rejected every production browser WebSocket with 403 because only the dev origins were allowed; `CENTRIFUGO_ALLOWED_ORIGINS` now sets them.
- `docker-compose.yml`: `celery-worker-prod`, `celery-beat-prod`, and `flower` inherited the image healthcheck for Django on port 8000 and stayed unhealthy, so `up --wait` failed. The worker now answers `celery inspect ping`, Flower probes port 5555, and beat disables the check.
- `nginx/nginx.conf`: the static `upstream` pinned the `django-prod` container IP at startup, so recreating `django-prod` during a deploy left nginx returning 502. Both upstreams now resolve per request.
- `scripts/deploy.sh`: VPS quick deploy ran `git pull` and `up -d` without a build, so it restarted the old image and shipped no code. It now builds, migrates with the new image through `run --rm`, and only then replaces the containers, the same order as the full deploy; only the rollback marker and health check are skipped. The `--quick` help and the VPS dry-run output now describe those steps, and the dry run prints the real profile flags.
- `docker-compose.yml`: `celery-worker-prod` consumed only `-Q default,celery`, while `api/celery.py` routes `*cleanup*` tasks to `bulk` and email tasks to `emails`. The scheduled OTP and inactive-user cleanups never ran in production. The worker now consumes every configured queue, and the Helm chart default lists `default,emails,bulk`.
- `justfile`: `backend-profile` also accepted `TASK_BACKEND=django-q` and `django-rq`, which started the worker profile and then failed in `api/tasks/loader.py`. It now accepts only the loader's `django_q` and `django_rq`.
- `api/centrifugo.py`: `CentrifugoClient` logged an `error` payload from Centrifugo and returned it as a success, so a rejected publish looked delivered. It now raises `ExternalServiceError`.
- `single` / PaaS image: nothing served `/static/`, so the admin and API docs assets returned 404. `whitenoise` now serves collected static files; the `prod` nginx still serves them first.
- `mcp` service: django-ai-boost bound to `127.0.0.1` inside the container, so the published port 8001 was unreachable. It now binds `0.0.0.0` inside the container, and Compose publishes it on host loopback only.
- `api/settings/dev.py` forced the console email backend, so `just up-mail` never received mail. The backend now follows `EMAIL_BACKEND`; `.env.example` shows the Mailhog values, and `up-mail` and `up-mcp` start the configured worker too.
- OpenTelemetry was never initialized: `init_tracing()` had no caller and the images lacked the packages, so Jaeger received nothing. `OTEL_ENABLED=true` now starts tracing in `CoreConfig.ready()` (and fails loud if the packages are missing), the images install the `observability` extra, and dev workers export to `jaeger:4317`.
- `api/settings/dev.py`: runserver's autoreloader logged every watched file at DEBUG; it now logs at INFO.
- `docker-compose.yml`: dev `db` and prod `db-prod` shared the `postgres_data` volume, so a local prod run opened the dev database and failed with `password authentication failed`, or migrated it. Dev now uses `postgres_dev_data` and `valkey_dev_data`; `db-prod` and `db-single` keep `postgres_data`, so servers keep their data. **Upgrade step for local dev:** the dev stack starts with an empty database. To keep it, copy the old volume first: `docker run --rm -v <project>_postgres_data:/from -v <project>_postgres_dev_data:/to alpine cp -a /from/. /to/`. `scripts/db_setup.sh` now removes only the dev volume.
- `core/controllers/users_controller.py`: `/users/staff` and `/users/active` were declared after `/users/{user_id}`, which shadowed them. Static paths now come first.
- `POST /users/superuser` now passes snake_case fields explicitly when it creates the user.
- `docker-compose.yml`: `django-prod` sits behind the bundled nginx, but Ninja's trusted proxy count was 0, so throttles saw nginx's IP for every client and the login limit (20/min) applied to all users together. The prod profile now sets `NINJA_NUM_PROXIES=1`; `.env.deploy.example` explains when to raise it.
- `generate_feature graphql` produced an app that did not start. It inserted its `urls.py` imports inside the multi-line `todos.controllers` import (a `SyntaxError`); with `--app-name=core` it wrote the view to `core/graphql.py`, which the `core/graphql/` package shadowed; the generated resolvers imported their context type only for type checkers, so Strawberry could not resolve it; the view never built the app's context, so `info.context.user` failed; and `me` read `User.created_at`, which does not exist. The view is now `core/graphql_view.py`, imports go after the last import statement, and a `{ me { email } }` query returns the user for a valid JWT and `null` without one.
- CI: the test and gauntlet jobs installed only the `dev` extra, so the task contract tests could not import Huey, django-q2, django-rq, or Dramatiq. Both jobs now install the task-backend extras.

### Security
- `/api/realtime/connection-token` and `/api/realtime/subscription-token` had no authentication. Anonymous callers got subscription tokens for any channel (`sub` claim `None`). The controller now requires JWT, a user may subscribe only to their own `notifications:<user id>` channel, and a test fails when any new operation is public without being on an explicit allowlist.
- Upgraded dependencies to clear `pip-audit` advisories: Django 5.2.6 to 5.2.17, cryptography 46.0.1 to 50.0.1, pillow 11.3.0 to 12.3.0, urllib3 2.5.0 to 2.8.0, tornado 6.5.4 to 6.5.10, plus idna, anyio, click, orjson, and tablib; then pip 26.2.1, flask 3.1.3, werkzeug 3.1.9, python-engineio 4.14.0, python-socketio 5.17.0, and strawberry-graphql 0.327.7. Removed the unused `python-jose`, which pulled in `ecdsa` (an advisory with no fix). The only remaining advisory across all extras is `mcp`, pinned by `django-ai-boost`'s `fastmcp<4` requirement and used in the dev extra only.
- The dev stack published Postgres, Valkey, Django, Flower, Jaeger, Mailhog, and Centrifugo on every interface, so anyone on the same network could reach the dev database and cache. They now bind to `127.0.0.1`; set `DEV_BIND_ADDRESS=0.0.0.0` to expose them. The `prod` nginx and the `single` app still listen on all interfaces.

## [1.11.0] - 2026-08-15

### Added
- **Codebase Atlas** (`atlas/` app) — interactive isometric architecture map in the Unfold admin at `/admin/atlas/`. Blocks sized by real LOC per app, animated data-flow dots on edges, clickable data packets (request/response samples from the live OpenAPI schema plus masked audit-log bodies), drill-down into app components, and a playable request-flow trace. Generator: `python manage.py atlas` (or `make atlas`). Opt-in config via `ATLAS_ENABLED`, `ATLAS_DATA_PATH`, `ATLAS_CACHE_TTL`, `ATLAS_REAL_SAMPLES`; per-app prose via `atlas.py` modules (see `core/atlas.py`, `todos/atlas.py`) or `ATLAS_METADATA`. Staff-only, CSP-safe (static JS/CSS + same-origin JSON endpoint).
- **deepsec security scanning** (`docs/DEEPSEC.md`) — Makefile targets `deepsec-init`, `deepsec-scan`, `deepsec-review`, `deepsec-report`, `deepsec-revalidate` for the agent-powered [deepsec](https://github.com/vercel-labs/deepsec) vulnerability scanner, plus a CI workflow example.
- **Observability admin pages** — Health Check and Metrics now render as Unfold-styled staff pages at `/admin/observability/health/` and `/admin/observability/metrics/` instead of raw JSON/plain-text endpoints. The `/api/health/detailed` and `/api/metrics` endpoints stay unchanged for dashboards and Prometheus scrapers. The sidebar and dashboard quick links point at the new pages; the Flower (Celery) link appears only when `FLOWER_URL` is configured.
- **Celery worker health check** — the health page and `/api/health/detailed` now include a `celery` check (registered only when `TASK_BACKEND=celery`) that reports worker availability.
- **Release automation** (`scripts/release.py`, `make release`) — bumps the version across `pyproject.toml`, `api/settings/common.py`, the Makefile banner, and `VERSION`; retitles the CHANGELOG `[Unreleased]` section and inserts the compare link; syncs `uv.lock`; then commits, tags `vX.Y.Z`, and pushes. Default bumps the patch version; `make release VERSION=1.11.0` sets it explicitly; `--dry-run` previews the changes.

### Fixed
- `api/settings/common.py`: vcache cache backend path corrected to `django_vcache.backend.ValkeyCache` (the default `vcache` config crashed on any cache access with django-vcache 2.3.0).
- `docker-compose.yml`: `FLOWER_BASIC_AUTH` no longer uses required-var syntax, so `make up` works without the variable set; it defaults to `admin:password`.
- `Makefile`: deepsec targets renamed to `deepsec-*` to stop overriding the existing bandit `security-scan` target.
- `Makefile`: `make up` starts the core stack (db, valkey, django); `make up-full` starts everything. `build`, `down`, and `logs` cover all compose profiles.
- `docker-compose.yml`: container-to-container addresses (`DB_HOST`, `VALKEY_URL`, `REDIS_URL`, `CENTRIFUGO_URL`, OTEL endpoint, flower broker) are now fixed to compose service names. They were interpolated from `.env`, so a local-dev `DB_HOST=localhost` leaked into the containers and the django service could not reach Postgres.
- `docker-compose.yml`: Celery broker and result backend now use the `redis://` scheme (`redis://valkey:6379/0`). kombu has no `valkey://` transport, so flower and the celery workers failed with "No such transport: valkey". Host ports for postgres and valkey are configurable via `POSTGRES_PORT` / `VALKEY_PORT` to avoid clashes with local services.
- `core/admin/user_admin.py`: the user change form crashed with "'date_joined' cannot be specified ... non-editable field" because the custom `User` model marks `date_joined`/`updated_at` as `auto_now` and Django 5.2's base `UserAdmin` no longer declares `readonly_fields`. The admin now declares `readonly_fields` and explicit `fieldsets`/`add_fieldsets` that cover the custom profile, status, and preference fields.
- `templates/admin/observability/`: the Health and Metrics pages kept light status colors in dark mode because django-unfold's compiled CSS does not ship most `bg-*`/`dark:bg-*` shades. Status tints and kind badges now come from `core/static/observability/observability.css` with explicit `.dark` overrides.
- `atlas/static/atlas/atlas-scene.js`: the map fit now pads for the top edge labels and caps zoom at 1.3, so the top text stays visible on load instead of being clipped.

### Changed
- `core/audit/admin.py`: the AuditLog change form now autocompletes the user relation (`autocomplete_fields`) and the changelist shows a search help text.

## [1.10.0] - 2026-08-12

### Added
- **Deploy Notification** (`scripts/deploy.sh`) — `notify_deploy` POSTs a `deploy_complete` JSON envelope (`app`, `commit`, `env`, `frontend_url`, `backend_url`) to `DEPLOY_WEBHOOK_URL` after a successful provider deploy. Skips silently when the webhook is unset, respects `--dry-run`, and never blocks a deploy on an unreachable webhook.
- **Dependency Gate** (`scripts/check_dependencies.py`) — new gauntlet gate and pre-commit hook that fails when `pyproject.toml` changes without a matching `DEPENDENCIES.md` entry, so dependency additions get reviewed instead of silently merged.
- **Commit Message Style Hook** (`scripts/check_commit_msg.sh`) — commit-msg hook enforcing the tbaggery checks commitizen skips: subject ≤50 chars, no trailing period, body wrapped at 72 chars.

### Changed
- Pre-commit: registered the `dependencies` gate and `commit-msg-tbaggery` style checks as local hooks.
- `.env.deploy.example`: documented `DEPLOY_WEBHOOK_URL`, `DEPLOY_ENV`, `FRONTEND_URL`, `BACKEND_URL`.
- Version strings synced across `pyproject.toml`, `api/settings/common.py`, and `Makefile`.

## [1.9.0] - 2026-07-31

### Added
- **Convention Enforcement Gate** (`scripts/check_conventions.py`) — 12th gauntlet gate with 12 deterministic checks for AI anti-patterns: DRF imports, raw Schema usage, ModelSchema, ninja.Router, wrong decorator order, missing @handle_exceptions, unscoped queries, redeclared base model fields, missing __init__.py exports, pip usage, mocked ORM, unregistered controllers
- **Cross-Stack Convention Checker** (`scripts/check_cross_stack.py`) — 13th gauntlet gate for fullstack monorepos: naming consistency, schema parity, tooling consistency, rules consistency, gauntlet consistency
- **Four-Layer AI Defense System** spanning both backend and frontend:
  - Layer 1: System Prompt Injection (`.omp/APPEND_SYSTEM.md`) — non-negotiable guardrails injected into every AI session
  - Layer 2: Always-Apply Rules (`.omp/rules/`) — full convention references always in context
  - Layer 3: TTSR Mid-Generation Rules (`.omp/rules/ttsr-*.md`) — interrupts model mid-generation when it writes prohibited patterns
  - Layer 4: Deterministic Gauntlet Gates — post-generation pass/fail verification
- **Backend Convention Rules**: `backend-conventions.md`, `django-ninja-anti-patterns.md` (12 wrong/right examples)
- **Backend TTSR Rules**: `ttsr-framework-identity.md` (DRF/Schema/Router/ModelSchema interrupt), `ttsr-convention-violations.md` (decorator order/redeclared fields interrupt)
- **Frontend Convention Enforcement** in react-vite-boilerplate: `CLAUDE.md`, `.omp/APPEND_SYSTEM.md`, `.omp/rules/react-conventions.md`, `.omp/rules/react-anti-patterns.md`, `.omp/rules/ttsr-react-anti-patterns.md`, `scripts/check_conventions.ts` (8 TypeScript convention checks), `package.json` gauntlet scripts
- **Portable Gauntlet Export** (`make export-rules`) — bundles all 16 convention enforcement artifacts for use in any codebase
- **Adoption Prompt** (`docs/ADOPTION_PROMPT.md`) — copy-paste prompt to install the gauntlet in any codebase via AI
- **Mattstack Integration Docs** (`docs/MATTSTACK_INTEGRATION.md`) — division of labor between gauntlet gates and mattstack audit
- **Admin Dashboard Stats** (`core/admin/dashboard.py`) — system health metrics for django-unfold admin

### Fixed
- **58 convention violations** across the codebase: 35 schemas using raw `ninja.Schema` instead of `CamelCaseSchema`, 7 controllers missing `@handle_exceptions()`, 7 models redeclaring base fields, 5 `__init__.py` files missing exports, DRF import in code generator, pip install in Makefile

### Changed
- CI: `actions/upload-artifact@v4` → `@v7`
- Gauntlet expanded from 10 to 12 gates (added CONVENTIONS at #5, CROSS-STACK at #6)
- Makefile: added `check-conventions`, `check-cross-stack`, `export-rules` targets
- Pre-commit: added convention enforcement hook
- Dependabot: labels require repo setup (create `ci`, `dependencies` labels in GitHub)

## [1.8.0] - 2026-07-24

### Added
- **Constraint Tools Philosophy** — formalized the approach inspired by [Uncle Bob Martin's SwarmForge](https://github.com/unclebob/swarm-forge): agents write the deterministic tools that check constraints. Small programs, binary pass/fail, no human judgment required. If code survives all constraint tools, you don't need to read it. Documented in `docs/CONSTRAINT_TOOLS.md` and `CLAUDE.md`.
- **The Gauntlet** — 10-gate quality pipeline implementing the constraint tools philosophy. Every code change must survive all gates before merge:
  1. FORMAT (ruff format --check)
  2. LINT (ruff check — 50+ rule categories)
  3. TYPECHECK (mypy)
  4. SECURITY (bandit)
  5. ARCHITECTURE (layer enforcement)
  6. FILELENGTH (max 400 lines)
  7. TEST (pytest --cov-fail-under=35)
  8. MUTATION (mutmut — test quality validation)
  9. AUDIT (pip-audit — dependency vulnerabilities)
  10. DEPLOY (manage.py check --deploy)
- **Architecture enforcement** (`scripts/check_architecture.py`) — validates Controllers → Services → Models layering, prevents cross-app controller coupling, detects reverse dependencies. Works in both standalone and mattstack-scaffolded layouts.
- **Gauntlet orchestrator** (`scripts/gauntlet.py`) — runs all gates with `--quick`, `--ci`, `--fail-fast`, `--gate`, `--report` modes. Generates JSON reports for CI artifact upload.
- **Mutation testing** via `mutmut` — validates that tests actually catch bugs, not just execute code paths.
- **Makefile targets**: `gauntlet`, `gauntlet-quick`, `gauntlet-ci`, `gauntlet-gate`, `check-arch`, `mutation-test`, `mutation-results`, `security-scan`, `check-file-length`
- **CI gauntlet job** — architecture check, file length check, and full gauntlet run as a GitHub Actions job with artifact upload
- **Pre-commit architecture hook** — validates layer constraints on every commit
- **Commitizen commit-msg hook** — enforces conventional commit format
- **Constraint tool template** — documented pattern for writing new gates: deterministic, <400 lines, binary pass/fail, agent-writable. See `docs/CONSTRAINT_TOOLS.md`.

### Changed
- **Coverage threshold** raised from 25% to 35% (ratchet toward 80%) — every PR must maintain or increase coverage
- **VS Code settings** migrated from deprecated ruff-lsp to native Ruff extension (`ruff.nativeServer: "on"`, removed `ruff.showNotifications`)
- **Security scanning** in CI is now mandatory (bandit runs as a blocking gate, not `|| true`)
- **CLAUDE.md** expanded with gauntlet documentation, Definition of Done checklist, architecture rules, and mattstack-cli integration notes
- **`check-all` Makefile target** now delegates to `gauntlet --quick` instead of individual commands

### Dependencies
- Added (dev): `mutmut>=3.2.0`, `bandit[toml]>=1.8.0`, `commitizen>=4.1.0`

## [1.7.0] - 2026-07-04

### Changed
- **CLAUDE.md rewritten** — slim, Karpathy-inspired behavioral guidelines with 5 principles (ask don't assume, match complexity, surgical changes, flag uncertainty, suggest better approaches)
- **Version strings synced** — `pyproject.toml`, `api/settings/common.py`, and `Makefile` all report `1.7.0` (were drifted at `1.2.0` in settings/Makefile)
- **Consolidated env files** — removed duplicate `env.example`, canonical file is `.env.example` with all env vars documented (Valkey, task backends, API keys, JWT, email, Centrifugo, Stripe, OAuth)
- **Pre-commit ruff version** — bumped `v0.13.2` → `v0.15.10` to match `pyproject.toml`
- **Ruff isort known-first-party** — added all Django apps (billing, files, webhooks, organizations, notifications)
- **Hatch wheel packages** — added all satellite apps to `[tool.hatch.build.targets.wheel]`
- **Makefile cleanup:**
  - Fixed `install`/`sync`/`install-dev` to use `uv sync` instead of `uv pip install/sync`
  - Deduplicated `health`, `celery-worker`, `db-restore` targets (renamed duplicates to `local-*` and `db-restore-mgmt`)
  - Removed stale `env.example` fallback from `setup-env`
  - Added `typecheck`, `check-all`, `up-observability` targets
  - Synced version display to `v1.7.0`
- **Production settings fixes:**
  - Removed invalid `MAX_CONNS`/`MIN_CONNS` DB options (pgbouncer-only), added `CONN_HEALTH_CHECKS`
  - Fixed CSP to use django-csp 4.x `CONTENT_SECURITY_POLICY` dict format (was using legacy `CSP_*` vars)
- **Dev settings cleanup** — removed dead commented-out code (SQLite fallback, debug toolbar INSTALLED_APPS, django-extensions), removed orphaned `RUNSERVER_PLUS_PRINT_SQL`
- **Docker Compose** — added `VALKEY_URL` to celery-worker and celery-beat services, fixed header comment (`redis` → `valkey`)
- **Module exports** — `core/schemas/__init__.py` now exports API key schemas, `core/security/__init__.py` exports `APIKeyAuth`

## [1.6.0] - 2026-07-04

### Added
- **Valkey as default cache/broker** — wire-compatible Redis fork (BSD license) using `valkey/valkey:8-alpine` Docker image. Configurable via `CACHE_BACKEND` env var with three options:
  - `vcache` (default) — django-vcache with Rust I/O driver for maximum performance
  - `valkey` — django-valkey, stable fork of django-redis
  - `redis` — original django-redis backend for backward compatibility
- **API Key authentication** — built-in machine-to-machine auth via `X-API-Key` header
  - `APIKey` model with prefix-based lookup and SHA-256 hashed secrets
  - Scoped permissions (e.g., `read:todos`, `write:todos`)
  - Key rotation, revocation, and expiry support
  - CRUD endpoints at `/api/api-keys/` (JWT-protected)
  - Django admin integration via Unfold
- **Global orjson renderer** — 2-10x faster JSON serialization for all API responses
  - `ORJSONRenderer` and `ORJSONParser` for Django Ninja
  - Native datetime, UUID, dataclass, and numpy handling
- **Pluggable task queue backends** — `TASK_BACKEND` env var with full parallel support:
  - Celery (default, unchanged)
  - Huey (`uv sync --extra huey`)
  - django-q2 (`uv sync --extra django-q`)
  - django-rq (`uv sync --extra django-rq`)
  - Abstraction layer: `from api.tasks import shared_task`
  - Docker Compose profiles for each backend
- **ty type checker** — Astral's Rust-based type checker alongside mypy (`make ty`)
- **New documentation:**
  - `docs/TASK_BACKENDS.md` — comparison and setup guide for all task queue options
  - `docs/API_KEYS.md` — API key auth guide with usage examples
  - `docs/MIGRATION.md` — step-by-step migration guide for existing codebases

### Changed
- Docker Compose services renamed: `redis` → `valkey` (volumes: `redis_data` → `valkey_data`)
- `VALKEY_URL` is the new canonical env var (`REDIS_URL` kept as fallback alias)
- Celery broker/result URLs default to `VALKEY_URL` instead of `REDIS_URL`
- Makefile: new `valkey-*` targets, `redis-*` kept as aliases
- Railway deployment config updated for Valkey template

### Dependencies
- Added: `django-valkey>=0.4.1`, `django-vcache>=0.1.0`
- Added (optional): `huey>=2.5.0`, `django-q2>=1.7.0`, `django-rq>=2.10.0`, `rq>=1.16.0`
- Added (dev): `ty>=0.0.1a1`

## [1.5.1] - 2026-04-14

### Added
- **Reusable HTTP client** (`api/utils/http_client.py`) — async/sync wrapper around httpx
  - Pydantic `response_model` for automatic response parsing via `TypeAdapter`
  - Configurable retries, timeouts, and expected status code validation
  - `HttpClientError` with status code and response body for structured error handling
  - Module-level `http_client` singleton for zero-config usage
- **Granian migration prompt template** — step-by-step guide in `.context/PROMPTS.md` for swapping Gunicorn to Granian (Rust-based WSGI/ASGI server), covering Dockerfile, docker-compose, k8s, PaaS, logging, and optional ASGI mode
- **Mermaid diagram upgrades** — converted all ASCII box diagrams in `docs/ARCHITECTURE.md` and `docs/REALTIME.md` to Mermaid for native GitHub rendering

### Changed
- **Bumped all dependencies to latest versions**
  - Django ecosystem: django-environ 0.13.0, cors-headers 4.7.0, debug-toolbar 5.2.0, flags 5.0.14, import-export 4.3.7, js-asset 3.1.0, storages 1.14.6, unfold 0.52.0, ninja-extra 0.31.3, ninja-jwt 5.4.3, celery 5.5.2, celery-beat 2.7.0
  - Infrastructure: redis 7.4.0, flower 2.0.1, httpcore 1.0.9, uvloop 0.22.1, gunicorn 25.3.0, python-dotenv 1.2.2, charset-normalizer 3.4.7
  - Dev/testing: ruff 0.15.10, pytest 9.0.3, pytest-django 4.12.0, pytest-cov 6.2.1, pytest-mock 3.14.0, factory-boy 3.3.3
  - CLI deps: typer 0.24.1, rich 15.0.0, jinja2 3.1.6, pyyaml 6.0.3, questionary 2.1.1
  - CI actions: codecov/codecov-action v5→v6, softprops/action-gh-release v2→v3

### Removed
- **`requests`** — completely unused; httpx covers all HTTP client needs
- **`uvicorn`** — project uses WSGI (Gunicorn), not ASGI
- **`click`** — transitive dependency via Celery, no direct usage
- **`rich`** (root) — only used in CLI package, which declares its own copy

## [1.5.0] - 2026-03-30

### Added
- **Pydantic camelCase aliases** — automatic snake_case ↔ camelCase conversion for API schemas
  - `AliasPath` support for nested field access
  - `populate_by_name=True` for dual snake_case/camelCase input acceptance
- **Comprehensive LLM prompt templates** — framework-aware code generation prompts in `.context/`

## [1.4.0] - 2026-03-20

### Added
- **K3s deployment support** — lightweight Kubernetes deployment using plain YAML manifests
  - `deploy/k3s/namespace.yaml` — dedicated namespace
  - `deploy/k3s/secrets.yaml` — centralized secrets management with fail-safe placeholders
  - `deploy/k3s/configmap.yaml` — application configuration
  - `deploy/k3s/postgres.yaml` — PostgreSQL with local-path PVC (k3s default storage)
  - `deploy/k3s/redis.yaml` — Redis with password authentication and persistence
  - `deploy/k3s/django.yaml` — Django deployment (2 replicas) with init container migrations
  - `deploy/k3s/celery.yaml` — Celery worker and beat deployments
  - `deploy/k3s/ingress.yaml` — Traefik ingress (k3s built-in) with rate limiting middleware
  - `deploy/k3s/README.md` — full deployment guide with k3s vs k8s comparison
- **Nginx security headers** — HSTS with preload, `Permissions-Policy`, `X-Permitted-Cross-Domain-Policies`

### Changed
- **Hardened rate limits** — login and token verification endpoints increased from 10 to 20 req/min for better UX while maintaining brute-force protection
- **Tightened Content-Security-Policy** — removed `unsafe-inline`, `http:`, `blob:`; restricted `default-src` to `'self'`
- **Updated `X-XSS-Protection`** — changed from `1; mode=block` to `0` per modern best practice (CSP replaces it)
- **Stricter `Referrer-Policy`** — changed from `no-referrer-when-downgrade` to `strict-origin-when-cross-origin`

### Security
- **Fixed shell injection in `docker-entrypoint.sh`** — replaced inline Python heredoc (which interpolated env vars directly into code) with the safe `create_superuser` management command
- **Removed hardcoded fallback secrets from `docker-compose.yml`** — `SECRET_KEY`, `CENTRIFUGO_API_KEY`, `CENTRIFUGO_TOKEN_SECRET`, and `FLOWER_BASIC_AUTH` now use `${VAR:?must be set}` syntax that fails fast if env vars are missing, instead of falling back to guessable defaults like `admin:admin`

## [1.3.0] - 2026-02-26

### Added
- **Four progressive Todo controller patterns** — declarative, basic, partial, and full service-layer
  - `todos/controllers/todo_controller_declarative.py` — explicit `try/except`, no decorator magic
  - `todos/controllers/todo_controller_basic.py` — minimal, `get_object_or_404`, no custom decorators
  - `todos/controllers/todo_controller_partial.py` — `@handle_exceptions` + `@log_api_call` on writes only
  - `todos/controllers/todo_controller.py` — full decorator stack + injected `TodoService`
- **TodoService** (`todos/services/todo_service.py`) — extracted all business logic from the controller into a dedicated, testable service layer
- **Resend email backend integration** — `django-anymail[resend]` as default mailer with console fallback
- **Smoke test suite** — lightweight tests verifying all 4 controller route prefixes are reachable
- **Google-style docstrings** across all controllers and services
- **CLI `--docstrings` flag** — generated projects include Google-style docstrings by default
- **CLI `--email-backend` flag** — select email backend (Resend, console, SMTP) during project generation
- **Centrifugo Real-Time Messaging** — standalone WebSocket server replacing Django Channels
  - `api/centrifugo.py` — JWT token generation and HTTP client for publishing
  - Token endpoints: `POST /api/realtime/connection-token` and `/subscription-token`
  - Centrifugo server config with chat, notifications, and organization namespaces
  - Docker Compose service under `realtime` profile (port 8800)
  - Nginx WebSocket proxy at `/centrifugo/`
  - `make up-realtime` command
  - Full documentation at `docs/REALTIME.md`
  - 15 unit tests for token generation and client methods
- **`todos/README.md`** — dedicated docs for the todos example app with pattern table and code examples
- **`docs/ARCHITECTURE.md` — Progressive Controller Patterns section** with ASCII diagram, pattern comparison, and decorator stack diagram

### Changed
- `TodoController` now delegates all operations to an injected `TodoService`; controller methods are one-liners
- Bandit security scan moved to pre-push hook (was blocking commits on every save)
- Replaced Django Channels consumer templates with Centrifugo service templates in code generators
- Removed `channels` and `channels-redis` dependencies from chat and notification generators
- Updated notification generator `_send_in_app` to publish via Centrifugo
- Updated `make up-full` and `make down-full` to include `--profile realtime`

## [1.2.0] - 2026-02-17

### Added
- **Test settings module** (`api/settings/test.py`) - SQLite locally, PostgreSQL in CI
- **Resend email integration** (`django-anymail[resend]`) - Default mailer with console fallback
- **CLI `add-app` command** - Scaffold new Django apps with model/controller/schema/test stubs
- Missing migration for `deleted_at` and `deleted_by` fields on Todo model
- `ordering = ["-created_at"]` on Todo model Meta

### Changed
- Updated minimum Python version from 3.12 to **3.13** (supports 3.13 and 3.14)
- Updated default Python version in CI from 3.14 to **3.13**
- Updated CI test matrix to Python 3.13 + 3.14 (dropped 3.12)
- Updated Dockerfile base image from `python:3.14-slim` to `python:3.13-slim`
- Updated ruff target version from `py312` to `py313`
- Updated CLI tool to v1.2.0 with enhanced version output
- Updated CLI `test` command to set `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated UV version in CI from 0.5.0 to 0.6.0
- Updated pytest to use `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated pre-commit default Python from 3.14 to 3.13
- Updated all `pip install` references to `uv add`
- Updated all documentation to reflect Python 3.13+ requirement

### Fixed
- Fixed test suite to run locally without PostgreSQL (SQLite fallback)
- Fixed `test_signup` test URL from `/api/users/signup` to `/api/auth/signup`
- Fixed Todo model missing `deleted_at`/`deleted_by` migration (schema mismatch)
- Fixed Todo model ordering (was unspecified, now `-created_at`)
- Fixed CLI `lint` command dead code in formatter branch
- All 26 tests now pass locally and in CI

## [1.1.0] - 2026-02-05

### Added
- **Audit Logging System** - Comprehensive compliance tracking (GDPR, SOC2, HIPAA ready)
  - Automatic model change tracking via Django signals
  - API request/response logging middleware
  - Authentication event tracking (login, logout, failures)
  - Immutable audit trail with preserved user emails
  - Admin interface for viewing and filtering logs
  - REST API endpoints for audit log queries

- **Feature Flags System** - Gradual rollouts and A/B testing
  - Boolean, percentage-based, and A/B test flag types
  - User and environment targeting
  - Time-based activation windows
  - Middleware for automatic flag attachment to requests
  - Admin panel management with bulk actions
  - REST API for flag management and evaluation

- **Observability Stack** - Production monitoring
  - OpenTelemetry distributed tracing with Jaeger integration
  - Prometheus metrics endpoint (`/api/metrics`)
  - Structured JSON logging with trace context
  - Enhanced health checks with component status
  - Request timing and slow request logging
  - Docker Compose profile for observability services

- **Task Management Improvements** - Enhanced Celery task handling
  - Progress tracking with `ProgressTask` base class
  - Dead Letter Queue (DLQ) for failed tasks
  - Periodic task scheduling API
  - Task status and progress REST endpoints
  - `TaskResult` model for persistent task tracking
  - Bulk retry and resolution for failed tasks

- **Testing Utilities** - Comprehensive testing toolkit
  - Contract tests with Schemathesis for OpenAPI validation
  - Load tests with Locust for performance testing
  - Enhanced test client with auth helpers
  - Custom assertions for API responses
  - Factory utilities for test data generation

- **OpenAPI Enhancements** - SDK generation and API tools
  - TypeScript SDK generator
  - Python SDK generator
  - Postman collection export
  - Insomnia collection export
  - API changelog generator for version comparison
  - OpenAPI spec validation

- **GraphQL Generator** - Optional Strawberry GraphQL setup
  - Management command to scaffold GraphQL for any app
  - JWT-authenticated GraphQL endpoint
  - Query and mutation types with examples
  - Custom context class with user access

### Changed
- Updated Python requirement to 3.13+ (from 3.11+)
- Updated all Dockerfiles to Python 3.13-slim
- Updated CI actions to latest versions (checkout@v6, setup-python@v6, setup-uv@v7)
- Consolidated `get_client_ip` utility to single canonical source
- Split pagination module into subpackage (`api/pagination/`)
- Split throttling module into subpackage (`api/throttling/`)
- Added `OffsetPaginator` and `TokenBucketRateLimiter` aliases for clarity

### Removed
- Legacy `todo_controller_legacy.py`
- Unused flake8 and isort configuration files (Ruff handles all linting)

## [1.0.0] - 2026-01-26

### Added
- **Developer Experience (DX) Overhaul**
  - One-command setup: `make setup` for complete project bootstrap
  - Environment doctor: `make doctor` validates Python, Docker, ports, and config
  - Docker Compose profiles for flexible service management:
    - `make up` - Core services (db, redis, django)
    - `make up-celery` - With Celery worker and beat
    - `make up-monitoring` - With Flower dashboard
    - `make up-full` - All services
  - `.env.development` with sensible defaults (committed)
  - `.dockerignore` for optimized Docker builds
  - VSCode configurations (settings, launch, tasks, extensions)
  - VERSION file for semantic versioning
  - CHANGELOG.md following Keep a Changelog format

- **CLI Tool (`django-ninja-matt`)**
  - Interactive project scaffolding with Typer + Rich
  - Commands: `dnm init`, `dnm doctor`, `dnm setup`
  - Standalone API and Monorepo project types
  - Feature selection (Celery, Redis, auth methods)
  - Deployment target configuration

- **Deployment Configurations**
  - Single-container Dockerfile for PaaS (`deploy/docker/Dockerfile.single`)
  - Railway configuration (`deploy/paas/railway.json`, `railway.toml`)
  - Render Blueprint (`deploy/paas/render.yaml`)
  - Kubernetes Helm chart with:
    - Backend deployment with health checks
    - Celery worker deployment
    - Celery beat deployment
    - Flower monitoring deployment
    - PostgreSQL and Redis subcharts
  - `docker-compose.single.yml` for single-container local testing

- **CI/CD**
  - GitHub Actions workflow for lint, test, Docker build
  - Security scanning with pip-audit
  - Automated releases workflow
  - Dependabot configuration for dependency updates

- **Infrastructure**
  - Celery worker and beat services in Docker Compose (profile-based)
  - Flower monitoring service (profile-based)

### Changed
- Enhanced `scripts/setup.sh` with `--auto` mode for CI/CD
- Improved Makefile with profile-based commands
- Updated docker-compose.yml with service profiles

## [0.8.0] - 2026-01-25

### Added
- OTP (One-Time Password) authentication support
- New user model fields including metadata
- Base model, service, and schema patterns
- SQL dump/restore commands
- Rate limiting middleware
- New make commands for data management

### Changed
- Updated user model with enhanced fields
- Improved authentication decorators

## [0.7.0] - 2026-01-20

### Added
- Django Ninja JWT authentication
- Custom user model with email-based auth
- Todo app as example CRUD implementation
- Comprehensive API documentation (Swagger/ReDoc)
- Health check endpoint
- Docker development environment with hot reload
- PostgreSQL 17 and Redis 7.2 services
- UV package management integration
- Ruff linting and formatting
- pytest test suite with coverage
- Pre-commit hooks configuration

### Changed
- Migrated from pip to UV for package management

## [0.6.0] - 2026-01-15

### Added
- Initial Django 5.2 + Django Ninja setup
- Basic project structure
- Docker Compose configuration
- Makefile for common operations

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.10.0 | 2026-08-12 | Deploy notification, dependency gate, commit-msg style checks |
| 1.9.0 | 2026-07-31 | Convention enforcement, cross-stack checker, four-layer AI defense |
| 1.8.0 | 2026-07-24 | The Gauntlet, constraint tools, mutation testing, architecture enforcement |
| 1.7.0 | 2026-07-04 | CLAUDE.md rewrite, version sync, env consolidation, Makefile cleanup |
| 1.6.0 | 2026-07-04 | Valkey, API keys, orjson, pluggable task queues, ty type checker |
| 1.5.1 | 2026-04-14 | Dep cleanup, HTTP client, Mermaid diagrams, granian prompt |
| 1.5.0 | 2026-03-30 | Pydantic camelCase aliases, LLM prompt templates |
| 1.4.0 | 2026-03-20 | K3s deployment, security hardening, nginx headers |
| 1.3.0 | 2026-02-26 | 4 controller patterns, TodoService, Resend, Centrifugo real-time |
| 1.2.0 | 2026-02-17 | Python 3.13+ default, test fixes, migration fixes |
| 1.1.0 | 2026-02-05 | Audit logging, feature flags, observability, task management |
| 1.0.0 | 2026-01-26 | DX Overhaul, CLI tool, K8s Helm chart |
| 0.8.0 | 2026-01-25 | OTP, enhanced user model, rate limiting |
| 0.7.0 | 2026-01-20 | JWT auth, UV, Docker dev environment |
| 0.6.0 | 2026-01-15 | Initial release |

[Unreleased]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.12.0...HEAD
[1.12.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.8.0...v1.0.0
[0.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/releases/tag/v0.6.0

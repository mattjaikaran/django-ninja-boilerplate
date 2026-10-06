# TODO

## Follow-ups

- [ ] Refine `scripts/check_dependencies.py` to flag only actual dependency-list changes in `pyproject.toml`. Currently any change — version bump, description, tool config — trips the gate and requires a `DEPENDENCIES.md` edit.

## 2026 environment hardening

Rules: no GitHub Actions (no CI budget). Every gate runs locally through
`just gauntlet` and git hooks. Agents must not write bulk tests (see
"Test discipline"). Stay on Django 5.2 until the Django 6 blockers clear.

### Test discipline (agent bloat control)

- [x] Add a "Testing policy" section to `AGENTS.md`: write a test only for a
  bug fix (regression), a changed public contract, or a boundary/permission
  rule. No tests for wiring, getters, schema echo, or mock calls. One test
  file per change at most. Never add tests to hit a coverage number.
- [x] Add a TTSR rule in `.omp/rules` that fires when an agent creates more
  than one new test file per task or a test with no assertion on behavior.
- [x] Keep `just test` fast: default run is `pytest -x -q --no-cov` on changed
  paths; full coverage runs only in `just gauntlet`.
- [x] Audit existing `tests/` and delete tests that pin wording, defaults or
  copies. Report the deleted count and the time saved.
  Done 2026-10-05: deleted 12 tests (9 in `tests/smoke/test_smoke.py` that
  copied `core/tests`/`todos/tests`, 3 in `test_settings_modules.py` that
  pinned defaults) and one wording assertion. Those two files went from 37
  tests in 21.3s to 25 in 17.2s (about 4s saved, same machine, PostgreSQL).

### Local gates replace CI

- [x] Delete `.github/workflows/ci.yml`; move any unique steps into
  `just gauntlet`.
- [x] Install a `pre-push` hook that runs `just gauntlet-quick`.
- [x] Make `pip-audit` fail the gate (remove `|| true` equivalent in local
  gate and pre-commit); allow-list known advisories in a file with expiry.
- [x] Add local `trivy` (image) and `cyclonedx-py` (SBOM) as optional
  `just security-full` targets. First `just trivy` run (2026-10-05) found 4
  HIGH Python findings (msgpack 1.1.2, urllib3 2.7.0, setuptools 70.3.0)
  from pip's vendored copies in the base image
  (`/usr/local/lib/python3.13/site-packages/pip/_vendor/vendor.txt`; the
  locked `/opt/venv` was correct), plus 7 HIGH Debian openssl findings.
  The production stage now uninstalls pip and the base stage runs
  `apt-get upgrade`. Rescan 2026-10-05: 0 HIGH/CRITICAL findings, no pip or
  setuptools in the image, `libssl3t64` 3.5.7-1~deb13u3.

### Version and hook drift

- [x] Make `pyproject.toml` the only version source: pre-commit `ruff` rev
  must equal the ruff pin (currently both 0.15.10 but `mirrors-mypy` is
  v1.14.0 and prettier is a v4 alpha). Replace pre-commit mirrors with
  `repo: local` / `language: system` hooks that run `uv run ruff|mypy`, so
  hooks cannot drift from the lockfile.
- [x] Remove `djangorestframework-stubs` from hook deps (DRF is banned).
- [ ] Remove the prettier hook if no JS files remain after the SPA cleanup.
  Checked 2026-10-05: `atlas/static/atlas/*.js` remain, so the hook stays. It
  now runs `bunx prettier@3.9.9` (same results as the v4 alpha on this tree).
- [x] Add `scripts/check_version_drift.py` to the gauntlet: compares ruff,
  mypy, uv, python, postgres and valkey versions across `pyproject.toml`,
  Dockerfile, compose, and `.pre-commit-config.yaml`.
- [x] Pin uv in the Dockerfile with
  `COPY --from=ghcr.io/astral-sh/uv:<pin>`; drop the curl install.
- [x] Fix license: `pyproject.toml` says `Proprietary`, README badge says MIT.
- [x] Remove obsolete `SECURE_BROWSER_XSS_FILTER`; remove stray
  "Transformers" Dockerfile comment; fix OCI label version.

### Database driver and pooling (one change, not three)

Django 5.2 ignores `OPTIONS["pool"]` with psycopg2. Pooling needs psycopg 3.

- [x] Replace `psycopg2-binary` with `psycopg[binary,pool]` (psycopg 3) and
  `opentelemetry-instrumentation-psycopg` for `...-psycopg2`.
- [x] Set `CONN_MAX_AGE = 0` in common and prod settings. Remove
  `CONN_MAX_AGE` 600/60. Keep `CONN_HEALTH_CHECKS` only if it is valid
  with pooling; verify against the 5.2 docs.
- [x] Add `OPTIONS = {"pool": {"min_size": ..., "max_size": ...}}` sized
  from env, and check `max_size` x workers fits Postgres `max_connections`.
- [x] Check Celery, Huey, RQ and Dramatiq workers: pooled connections do not
  mix with forked workers. Smoke-test each enabled backend.
- [x] Check pgvector `VectorField` registration works on psycopg 3
  (`pgvector.psycopg` register).

### ASGI

- [x] Switch production to ASGI (uvicorn workers under gunicorn, or
  granian). Update `Dockerfile` production stage, entrypoint, compose
  healthcheck, and nginx upstream.
- [ ] Confirm sync Ninja views, Channels/Centrifugo paths and observability
  middleware work under ASGI. Do this after the psycopg 3 change, not
  before: async + pooled connections are the point of both.

### OpenAPI as the single type contract

- [x] Export a committed `docs/openapi/openapi.json` with
  `just openapi` (deterministic key order). Add `just openapi-check`
  that fails when the committed file differs from the generated one;
  put it in `gauntlet-quick`.
- [x] Make Pydantic constraints explicit so they reach OpenAPI: `Field`
  `min_length`, `max_length`, `ge`, `le`, `pattern`, enums, `Literal`. Zod
  generation reads only what OpenAPI carries.
- [x] Document `CamelCaseSchema`: OpenAPI must emit the camelCase aliases
  (`by_alias=True` in the export). Add one contract test that fails if the
  exported property names are snake_case.
- [x] Add `scripts/check_schema_parity.py`: for every request/response
  schema, assert the generated Zod schema (from the frontend) has the same
  fields, required-ness, nullability and constraints. Run from the
  monorepo via `mattstack sync check`.
  Done on the OpenAPI side: the frontend generates Zod from
  `openapi.json` (`@hey-api/openapi-ts`), so the script checks that the
  file carries every type and constraint. `mattstack sync check` is not
  wired yet (mattstack repo).
- [x] Forbid `dict`, `Any` and untyped `JsonField` in public schemas, or
  require an explicit `# schema-ok:` reason (check in
  `scripts/check_conventions.py`).

### Frontend serving cleanup

- [x] Find and remove SPA-serving remnants. I could not find a Django
  `serve_spa` view. Check these first: `nginx/nginx.conf` (`try_files`
  fallback), `Dockerfile`/compose frontend stages, `deploy/*` frontend
  manifests, and `cli/src/django_ninja_matt/generators/monorepo.py`
  (clones a frontend and emits `npm` targets; repo rule is `bun`).
- [x] Keep only `FRONTEND_URL`, CORS and CSRF settings that cookie auth needs.
- [x] Move the backend to an API-only contract: nginx proxies `/api`, `/admin`,
  `/static`, `/media`; the frontend is a separate container or origin.

### Auth for the BFF-style frontend

- [x] Add a cookie auth mode to `ninja-jwt`: httpOnly, Secure, SameSite=Lax
  access and refresh cookies, CSRF check on unsafe methods, and a
  `/auth/refresh` that rotates cookies. Frontends stop using `localStorage`.
- [x] Define and document the CSRF client contract (the frontend prompt
  depends on it):
  - `GET /api/auth/csrf` sets a readable (not httpOnly) `csrftoken` cookie
    and returns `{"csrfToken": "..."}`. Unauthenticated, no side effects.
  - Every POST/PUT/PATCH/DELETE, including `/auth/login` and
    `/auth/refresh`, must send `X-CSRFToken` equal to the cookie value.
    Missing or wrong token returns 403.
  - The client calls `/api/auth/csrf` once before login, then reads the
    `csrftoken` cookie for each unsafe request. After a 403 with code
    `csrf_failed`, refetch once and retry once.
  - Settings: `CSRF_COOKIE_HTTPONLY=False`, `CSRF_COOKIE_SAMESITE="Lax"`,
    `CSRF_COOKIE_SECURE` follows `USE_TLS`, `CSRF_TRUSTED_ORIGINS` includes
    the frontend origin, `CORS_ALLOW_CREDENTIALS=True`, `X-CSRFToken` in
    `CORS_ALLOW_HEADERS`.
  - Cross-origin dev: cookies need the same site. Prefer the frontend dev
    proxy so both share one origin.
- [x] Update CSP and CORS (`CORS_ALLOW_CREDENTIALS`) and the contract tests
  in `tests/contract/test_route_access.py`.

### AI and data layer (opt-in)

- [x] pgvector is already an add-on in the latest boilerplate. Verify the
  compose DB image is `pgvector/pgvector:pg17`, the `vector` extension
  migration exists, and `VectorField` + HNSW index example works.
  Checked 2026-10-05: pgvector was not in the repo. Added it in the `ai`
  extra; `POSTGRES_IMAGE=pgvector/pgvector:pg17` opts Compose in (default
  stays `postgres:17-alpine`). `ai.0001_initial` creates the extension;
  `EXPLAIN` on pg17 + pgvector 0.8.7 shows an index scan on the HNSW index.
- [x] Add `core/ai/`: provider-neutral LLM and embedding client (LiteLLM or
  OpenAI-compatible), embedding task through `api/tasks`, and OTel GenAI
  span attributes. No provider keys in code.
  OpenAI-compatible over httpx (no new SDK; reasons in docs/AI_LAYER.md).
- [x] Add hybrid search helper: Postgres FTS plus pgvector with reciprocal
  rank fusion.
- [x] Add compose profiles: `ai` (Qdrant, optional) and `graph`. Default
  graph option is Postgres recursive CTE or Apache AGE; Neo4j or FalkorDB
  only as an opt-in profile.
  Default: recursive CTE (`reachable`). `graph` profile: Neo4j 5.26 LTS.
- [x] Add an app-level MCP server exposing selected read-only Ninja routes
  (separate from the dev-only `django-ai-boost` profile). Auth required.
  `/api/mcp`, `MCP_ENABLED`, tools from `MCP_TOOLS` GET operationIds.
- [x] Cache LLM responses in Valkey with a hash-of-prompt key and TTL.

### Observability and security

- [x] Add Sentry (or GlitchTip) as an optional extra with scrubbed PII.
- [x] Add CodeQL-equivalent locally: `semgrep` with a pinned ruleset in
  `just security-full`. `just semgrep` pins semgrep 1.179.0 and a
  `semgrep-rules` commit (Django, JWT, Python security). First run
  2026-10-05: 50 findings on 464 files, not triaged yet.
- [ ] Raise the mypy and coverage bar in steps: drop one
  `disable_error_code` per week, raise the coverage floor from 30% in
  steps of 5%. Do not add tests only to raise coverage.
  Ratchet plan (never lower a step; one step per change):
  - Coverage: the floor lives in two places that must move together,
    `--cov-fail-under` in `[tool.pytest.ini_options] addopts` and
    `GauntletRunner.coverage_threshold` in `scripts/gauntlet.py` (the
    `--coverage` default reads it). Last measured line rate
    is 39.8% (`coverage.xml`, 2026-10-02). Raise the floor by 5 only when
    two consecutive `just gauntlet` runs measure at least the new floor + 2.
    Next steps: 35%, then 40%. Coverage rises from regression and contract
    tests that the testing policy allows, not from new tests written for it.
  - mypy: drop one code per week from the `[[tool.mypy.overrides]]` blocks,
    fix the errors it shows, then shrink the module list. Order: the
    26-module block (`union-attr`, `override`, `return-value`, `assignment`,
    `arg-type`, `attr-defined`, `var-annotated`), then
    `notifications.models.notification`, then the models `var-annotated`
    block, then `ignore_errors` on `core.sse.events`. No new
    `# type: ignore` without a written reason.

### Django 6 (blocked, track only)

- [x] Keep `Django>=5.2,<6` in the main pin. Keep the 6.0 run as a manual
  `just test-django6` target. List blockers in `DEPENDENCIES.md`
  (ninja-extra, ninja-jwt, django-unfold, django-csp, django-vcache).
  Checked 2026-10-05 on PyPI: the 6.0 blockers are `django-ninja-jwt`,
  `django-csp`, `django-import-export` and `django-storages` (no declared
  6.0 support). `ninja-extra` and `unfold` clear with a lock upgrade;
  `django-vcache` declares 6.0. The suite passes on 6.0.8.
- [ ] When the blockers clear, wrap native `django.tasks` in `api/tasks`
  instead of the custom Celery-first contract.

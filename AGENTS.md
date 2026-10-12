# AGENTS.md

Canonical guidance for every agent and harness. Read it before a non-trivial
change. Skills: `.agents/skills/` (index: `SKILLS.md`).

## 01 Hi, I'm the maintainer

Solo developer, design background. I run this production-ready Django Ninja
boilerplate on macOS (Apple Silicon) and deploy to a VPS and PaaS. I want code
obviously correct in six months, not clever today.

## 02 Talking to me

- Write plainly. Short sentences. One word, one meaning. No em dashes in
  generated content.
- Lead with the answer, then the evidence: the command you ran and what it
  printed. Do not summarize output you did not read.

## 03 Reading my prompts

- I dictate prompts: expect typos. Read for intent. Before you "fix" an odd
  phrase, check whether the codebase has a reason for it.
- I may use an old feature name; match it to what exists.

## 04 Doing the work

- Carry the change to a usable state: code, tests, docs and registration.
- Resolve routine uncertainty with repo conventions; do not stop to ask.
- Surface a material risk before you implement.
- Do not silently reduce scope. Say which part you cannot do and why.

## 05 Delegation

Give the agent its owned paths, the interface to honor, and how to verify.
Tell it to skip formatters, linters and the full suite. Verify its output.
Do not delegate the top-level plan.

## 06 Verification

- Verify each meaningful change by running it; a passing suite does not prove
  a new feature. Quote the actual output.
- Run `just gauntlet-quick` before you declare work complete.

## 07 My environment

- Docker via OrbStack. Task runner: `just` (old Makefile: `Makefile.legacy`).
- Local Postgres 17 with pgvector. `.env` targets host services
  (`DB_HOST=127.0.0.1`), `.env.development` the Compose `db` service;
  `just doctor` warns when they disagree.
- Tests use SQLite unless `TEST_DB=postgres`; `CI=true` does not change that.
- Start a session with `just doctor` (tools, `.env`, secrets, ports, load;
  exits 1 only on FAIL) and `just agent-status` (git, tickets, journeys, last
  gauntlet). Failed gates print a one-line fix hint.
- Ports: django 8000, mcp 8001, mailhog 8025, centrifugo 8800, flower 5555;
  Docker Postgres 5433 and Valkey 6380 (beside local 5432/6379). `just dev`
  moves a busy port to the next free one and prints it (`just check-ports`
  previews). Dev ports bind `127.0.0.1` (`DEV_BIND_ADDRESS`); only `prod`
  nginx and the `single` app listen on all interfaces.
- Preview `.env` secret changes with `python3 scripts/env_secrets.py fill
  --dry-run` before `just setup-env`.

## 08 Patterns We Do Not Use

### Django ORM and models

- No database access or `try/except` around ORM lookups in a controller: use
  a service and `get_object_or_404`.
- Never edit an existing migration; run `makemigrations`.
- Never hide invalid state with a fallback. Fail loud with
  `ImproperlyConfigured` or a 500 that carries the real error.
- No `.raw()` or `.extra()`: use the ORM, `Subquery` or `OuterRef`.
- `select_related`: forward FK and one-to-one. `prefetch_related`: reverse FK
  and many-to-many.
- Default base: `SoftDeleteModel` (`core.models.base`; other bases in
  `rule://backend-conventions`). Never redeclare `id`, `created_at`,
  `updated_at`, `created_by`, `updated_by`, `is_active`, `deleted_at`,
  `deleted_by` or `metadata`.
- Models: `{Name}` in PascalCase, `user` FK with
  `related_name="{name_plural}"`; fields, relationships and `Meta` only.

### Django Ninja

- Django Ninja Extra, not DRF: no `rest_framework`, serializers or viewsets.
  No `ninja.Router` or `views.py`: one `@api_controller` per file in
  `<app>/controllers/<name>_controller.py`. No `api/` directory inside an app;
  root `api/` is project configuration.
- Schemas inherit `CamelCaseSchema` (`core.schemas.base_schema`; never
  `ninja.Schema`, `ModelSchema`, or a redeclared `from_attributes = True`).
  One `<app>/schemas/<name>_schema.py` per domain (no `schemas/request.py` or
  `schemas/response.py`): `{Name}Schema`, `Create{Name}Schema`,
  `Update{Name}Schema` (all optional). UUIDs are `str`. `model_dump()`
  returns camelCase keys for responses and logs; pass ORM writes
  `model_dump_fields()` (snake_case field names).
- Use `Field(...)`, `Literal` or an `Enum` over a hidden `@field_validator`.
  Frontend Zod schemas come from `docs/openapi/openapi.json`: after a schema
  or route change, run `just openapi` and commit the file.
- Controllers validate, call `self.service` (set in `__init__`) and return
  `(status, data)`; business logic lives in services. Services extend
  `CRUDService[Model]` (`core.services.base_service`), set `model`, and
  override `get_queryset()` for related loading.
- Scope user data to `request.user`, never `Model.objects.all()`.
- Decorator order: `@http_*`, `@log_api_call()`, `@validate_request()` (if
  used), `@paginate(PageNumberPaginationExtra)` (list endpoints).
- Register controllers with `api.register_controllers(...)` in
  `api/urls.py`, where exception handlers are registered once. Raise
  `api.exceptions` errors or use `get_object_or_404`; there is no
  `handle_exceptions` decorator.
- Each `__init__.py` in `models/`, `schemas/`, `services/`, `controllers/`
  and `factories/` imports its public classes and sets `__all__`.
- Private controllers: `JWTAuth`. Public operations: `auth=None`. Staff-only:
  `IsAdminUser`.
- Review a new anonymous operation, then add its `(method, path)` to
  `PUBLIC_OPERATIONS` in `core/tests/test_route_auth.py`. Never add routes
  just to pass it: it fails on purpose for accidental public operations.
- Put static paths before every `/{id}` handler (including `PUT` and
  `DELETE`): Ninja binds a pattern where it first appears, so an earlier
  `/{id}` shadows a later static GET. CONVENTIONS (`ROUTE_ORDER`) and the
  smoke route sweep catch it; mark a deliberate case `# route-ok: <reason>`.
- Never exempt an endpoint from CSRF for a browser call. Unsafe methods need
  `X-CSRFToken` (`docs/COOKIE_AUTH.md`).

### Tooling, tasks and code

- `uv`, not `pip` or `poetry`. `bun`, not `npm` or `yarn`. `ruff`, not
  `black`, `isort` or `flake8`. `mypy` for types. `rg` or `just search`, not
  `grep -r`.
- Each new dependency needs a `DEPENDENCIES.md` entry.
- One `docker-compose.yml`: add services under a profile. A service that
  depends on `db` or `valkey` adds its profile to that service's `profiles`.
- `scripts/release.py` commits and tags unless `--dry-run`; it pushes only
  with `--push`, rejects unknown flags, and `--help` prints usage.
- Import `shared_task` from `api.tasks`, not Celery. Keep tasks
  backend-neutral: `.delay()`, and raise `.retry()` from the task handle. A
  new task backend is an optional extra plus a Compose profile; its loader
  fails loud without the package.
- No abstraction before a second real use case; no `import *`. Length cap:
  400 lines by default; `[tool.file-length]` in `pyproject.toml` sets the
  exceptions (for example 1200 in `scripts/`, 800 in `cli/`). Split, do not
  raise a cap.

## 09 The gauntlet (quality gate)

Every change passes these gates before merge.

| # | Gate | Tool | Catches |
|---|---|---|---|
| 1 | FORMAT | `ruff format --check` | Style drift |
| 2 | LINT | `ruff check` | Bugs, anti-patterns, dead code |
| 3 | TYPECHECK | `mypy` | Type errors, missing annotations |
| 4 | SECURITY | `bandit` | SQLi, XSS, hardcoded secrets |
| 5 | CONVENTIONS | `scripts/check_conventions.py` | DRF, raw `Schema`, decorator order, unscoped queries, redeclared fields, `Any`/bare `dict` fields without `# schema-ok:`, static paths after `/{id}` (`ROUTE_ORDER`), camelCase dumps written to the ORM (`CAMEL_DUMP_TO_ORM`) |
| 6 | DEPENDENCIES | `scripts/check_dependencies.py` | `pyproject.toml` change without a `DEPENDENCIES.md` entry |
| 7 | DRIFT | `scripts/check_version_drift.py` | Python/uv/Postgres/Valkey/hook versions differ across `pyproject.toml`, `uv.lock`, Dockerfiles, Compose, `.pre-commit-config.yaml` |
| 8 | ARCHITECTURE | `scripts/check_architecture.py` | Layer violations, cross-app coupling |
| 9 | OPENAPI | `manage.py export_openapi --check` | Stale `docs/openapi/openapi.json` |
| 10 | SCHEMA-PARITY | `scripts/check_schema_parity.py` | snake_case or untyped properties, required/nullable mismatches |
| 11 | FILELENGTH | `scripts/check_file_length.py` | Files over their cap |
| 12 | CROSS-STACK | `scripts/check_cross_stack.py` | Naming and schema parity (monorepo only) |
| 13 | JOURNEYS | `scripts/check_journeys.py` | Features, journeys, Playwright tags out of sync; `done`/checked without a passing e2e test |
| 14 | TICKETS | `scripts/tickets.py check` | Bad format, missing dependencies, colliding `ready` tickets |
| 15 | TEST | `pytest` | Broken smoke, contract, permission, regression tests |
| 16 | TEST-OPTIONAL | `pytest webhooks files` with `WEBHOOKS_ENABLED`, `FILES_ENABLED` | Flag-gated apps (kept out of default settings and OpenAPI) |
| 17 | CLI-TEST | `pytest cli/tests` | Broken `cli/` package |
| 18 | AI-DB | `scripts/test_ai_db.py` | Postgres-only tests (`core.ai` owner scoping, concurrent refresh) in a throwaway pgvector container; skips without Docker |
| 19 | DEPLOY-CHECK | `manage.py check --deploy` | Production config issues |

The full gauntlet adds GENERATORS (`scripts/check_generators.py`, `just
check-generators`: every generator in a throwaway worktree, then
`manage.py check`, pending migrations, ruff, generated tests), DOCKER
(production image; skips without Docker) and AUDIT
(`scripts/audit_dependencies.py`: `pip-audit` on `uv.lock`, always blocking;
allowlist an unfixed advisory in `pip-audit-allowlist.toml` with a reason and
expiry, and an expired entry fails).

No hosted CI. `just pre-commit-install` installs pre-commit, commit-msg and
pre-push hooks; pre-push runs `just gauntlet-quick` and the audit. Hooks are
`repo: local` via `uv run` or pinned `uvx`/`bunx`, matching the lockfile.

```bash
just gauntlet                 # every gate
just gauntlet-quick           # skip audit, docker (use while working)
just gauntlet-ci              # every gate, JSON report
just gauntlet-gate lint       # one gate by name
just openapi                  # regenerate docs/openapi/openapi.json
just openapi-check            # OPENAPI + SCHEMA-PARITY
just audit                    # pip-audit (blocking)
just security-full            # optional: bandit, audit, semgrep, SBOM, trivy
just test-django6             # manual: suite on Django 6.0 (unsupported)
```

Single-gate recipes: `just check-conventions`, `check-cross-stack`,
`check-arch`, `check-drift`, `check-journeys`, `tickets check`,
`security-scan` (bandit). Without `just`: `make -f Makefile.legacy
gauntlet-quick`.

### Architecture rules the checker enforces

1. Layers flow Controllers to Services to Models; no reverse imports.
2. Models never import schemas, services or controllers.
3. Cross-app calls go through services, not controllers.
4. Migrations never import controllers, services or schemas.

## 10 Definition of done

- [ ] The requirement works, not just the happy path
- [ ] `just test` and `just gauntlet-quick` pass
- [ ] User-visible changes update `docs/product/` and its Playwright tags
- [ ] A ticket's PR sets `status: done` in its ticket file
- [ ] No new linter warnings; architecture rules and length caps hold
- [ ] Type hints on all public interfaces
- [ ] Conventional Commits message (`type(scope): summary`)

Also (not fully gate-enforced): no commented-out code or `print()` in
production code; no `# type: ignore`, `# nosec` or `# noqa` without a reason.

### Testing policy

Write the fewest tests that catch a consumer-visible break, in three layers:

|Layer|Where|Proves|
|---|---|---|
|Smoke|`tests/smoke/`|No route returns a 5xx or an unexpected 422|
|Contract and boundary|`tests/contract/`, `<app>/tests/`|Auth, permissions, ownership, the OpenAPI contract, limits|
|E2E journeys|Playwright in the frontend|A user journey works end to end (section 13)|

Write a test only for: a bug fix (a regression test that fails before the
fix); a changed public contract (route, schema, status code, error shape, or
a setting clients or operators rely on); a boundary or permission rule (auth,
ownership, limits, validation edges); security-relevant pure logic (SSRF
checks, lockout math) as one table-driven test.

Do not write: unit tests for functions or helpers; model tests (fields,
`__str__`, defaults, `Meta`); tests that mock a collaborator (httpx, the ORM,
an SDK) and assert on the mock; tests of wiring, getters, schema echo,
defaults or copied constants; tests that repeat an API test or a journey;
tests for coverage. No coverage floor, no mutation testing.

Hit the real database (never `mocker.patch` the ORM); use Factory Boy for
data. Assert on behavior (response, database state, raised error, exact
value), not `mock.assert_called*`, `is not None`, `isinstance` or
`len(...) > 0`. At most one new test file per change; throwaway scripts stay
out of `tests/`. Do not copy tests listed in `docs/tickets/PRUNE_PLAN.md`;
tickets remove them.

`just test` runs changed-file tests and stops at the first failure; `just
test-all` runs all; `just test-coverage` only reports. TTSR rules
`.omp/rules/ttsr-test-new-file.md` and `ttsr-test-assertions.md` enforce this.

## 11 Constraint tools

`scripts/` checkers are deterministic gates (exit 0 pass, 1 fail) an agent
can extend: add the script under its length cap, a `_gate_*` method in
`scripts/gauntlet.py`, a `justfile` recipe, and a row in the section 09 table.

## 12 Where the guidance lives

| Path | Purpose |
|---|---|
| `AGENTS.md` | Canonical rules, gates and workflow |
| `SKILLS.md` | Index of `.agents/skills/` (loaded on demand) |
| `.omp/` | oh-my-pi: `APPEND_SYSTEM.md`, `rules/` (references, TTSR), `skills/` |
| `.context/` | `EXAMPLES.md`: worked examples |
| `docs/` | Architecture, migration, realtime, constraint tools |
| `docs/product/`, `docs/tickets/` | Features and journeys (section 13); worker tickets (section 14) |

`CLAUDE.md` is gitignored; never reference or rely on it.

## 13 Features, journeys and e2e tests

These three must agree; change all three together:

|Artifact|Path|Owner|
|---|---|---|
|Feature list|`docs/product/FEATURES.md`|Planner|
|User journeys and stories|`docs/product/journeys/J-NNN-*.md`|Planner|
|Playwright journey tests|Frontend `e2e/`: one test per journey tagged `@J-NNN`, steps titled `J-NNN-S<n>: ...`|Planner or worker|

- A checked feature (`[x]`) or `done` journey means a Playwright test proves
  it and its last run passed, never "the code exists".
- A failing journey test is a known issue: set the journey to `building`, add
  a `known_issues` entry naming a ticket, and fix it before closing the ticket.
- `just check-journeys` (JOURNEYS gate) enforces this; `/admin/journeys/`
  shows what each step is missing. `just sync-frontend <frontend path>`
  checks that frontend's Playwright report and OpenAPI copy against
  `docs/openapi/openapi.json`; `--check` exits 1 on drift.

Format and sync loop: `docs/product/README.md`, `journey-sync` skill.

## 14 Work modes and handoff

- Solo mode: the maintainer and planner model may commit to `main`.
- Worker mode: a smaller model runs only `tier: small` tickets from
  `docs/tickets/`, edits only the files its ticket lists, never pushes to
  `main`, and opens a PR from the bot GitHub account for review.
- The planner keeps the queue full of tickets that need no design decisions.
  `just tickets check` (TICKETS gate) blocks collisions.

`just worker-once` (preview: `--dry-run`) runs one iteration: claim, run
`$WORKER_AGENT_CMD` in a worktree, verify with one retry, then open a PR or a
draft `needs-planner` PR. Roles, machines, bot account, merge conflicts,
overnight loop: `docs/AGENT_HANDOFF.md`. Skills: `ticket-planner`,
`ticket-worker`.

After a scaffold, the first planner session fills `docs/product/` and the
first tickets. After each rejected PR, add the lesson below.

## When to add to this section

When you reject an implementation choice in review, add the lesson here before
the next session. Format: what not to do, what to do instead, and why. One line
per rule, no paragraphs.

- Do not let a smoke sweep accept 400 or 404 on a parameterless GET: it hid
  12 shadowed todo routes and 3 audit routes. Fail on any status of 400 or
  higher except 403 for regular users, because a list route has no input to
  reject.

## Reference library

Agent instruction patterns from open-source projects:
https://ossrules.md/llms.txt.

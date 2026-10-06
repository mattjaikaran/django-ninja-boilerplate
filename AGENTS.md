# AGENTS.md

Working notes for agents in this repository. Read this before a non-trivial
change. This file is harness-agnostic: it is the canonical guidance for any
agent, and the quality gate is in section 09. `.agents/skills/` holds
task-specific skills (see `SKILLS.md`).

## 01 Hi, I'm the maintainer

I'm a solo developer with a design background. I built this boilerplate to be a
production-ready Django Ninja starting point, and I run it locally on macOS
(Apple Silicon) and deploy it to a VPS and to PaaS. I care more about the code
being obviously correct six months from now than about it being clever today.

## 02 Talking to me

- Write plainly. Short sentences. One word, one meaning.
- Do not use em dashes in generated content.
- Lead with the answer, then the evidence.
- Show the command you ran and what it printed. Do not summarize output you did
  not read.

## 03 Reading my prompts

- I dictate prompts, so expect typos and run-on sentences.
- Read for intent, not for literal wording. If a phrase looks like a typo,
  check whether the codebase has a reason for it before "fixing" it.
- I may refer to a feature by an old name. Match it to what exists.

## 04 Doing the work

- Infer the intended outcome and carry the change through to a usable state:
  code, tests, docs, and registration.
- Resolve routine uncertainty yourself using the repo's conventions rather than
  stopping to ask.
- Surface a material risk before implementing, not after.
- Do not silently reduce scope. If part of the request cannot be done, say which
  part and why.

## 05 Delegation

When you delegate, give the agent everything it needs: the exact paths it owns,
the interface it must honor, and how to verify its own work. Tell it to skip
formatters, linters, and the full test suite. Verify its output before you
accept it. Do not delegate the top-level plan.

## 06 Verification

- Verify after every meaningful change. Run the thing, don't just reason about
  it.
- A passing test suite is not proof of a new feature; run the feature.
- Inspect actual output. Quote it.
- Run `just gauntlet-quick` before declaring work complete.

## 07 My environment

- macOS, Apple Silicon. Docker via OrbStack.
- Local Postgres 17 with pgvector, and `.env` points `DB_HOST=localhost`.
- `just` is the task runner. The old Makefile is `Makefile.legacy`.
- Ports: django 8000, mcp 8001, mailhog 8025, centrifugo 8800, flower 5555.
  The Docker stack publishes Postgres on 5433 and Valkey on 6380, offset from
  the local 5432/6379, so it can run beside local services.
  Dev ports bind to `127.0.0.1` (`DEV_BIND_ADDRESS`); only the `prod` nginx
  and the `single` app listen on all interfaces.

## 08 Patterns We Do Not Use

Agents fill missing context with familiar defaults. Those defaults are often
wrong here. Do not use them.

### Django ORM

- Do not access the database from a controller. Use a service.
- Do not edit an existing migration. Create a new one with `makemigrations`.
- Do not add fallback behavior that hides invalid state. Fail loud with
  `ImproperlyConfigured` or a 500 that carries the real error.
- Do not put `try/except` around ORM lookups in a controller. Use
  `get_object_or_404` so the exception handler maps it correctly.
- Do not use `.raw()` or `.extra()`. Use the ORM, `Subquery`, or `OuterRef`.
- Do not treat `select_related` and `prefetch_related` as interchangeable.
  `select_related` is for forward FK and one-to-one; `prefetch_related` is for
  reverse FK and many-to-many.

### Django Ninja

- Do not use DRF. No `rest_framework` imports, serializers, or viewsets.
- Do not use `ninja.Schema`. Every schema inherits `CamelCaseSchema`.
- Do not use `ModelSchema`. Write explicit Pydantic schemas.
- Do not use `ninja.Router` function-based views. Use `@api_controller`.
- Do not use `views.py` for endpoints. Controllers live in
  `<app>/controllers/<name>_controller.py`.
- Do not create an `api/` directory inside an app. The root `api/` package is
  project configuration.
- Do not use `schemas/request.py` or `schemas/response.py`. Use one
  `<app>/schemas/<name>_schema.py` per domain, with all three schemas.
- Do not put business logic in a controller. Controllers validate, call a
  service, and return.
- Do not write `Model.objects.all()` in a controller that returns user data.
  Scope to `request.user`.
- Do not put more than one controller in a file.
- Do not register a new controller without adding it to `api/urls.py`.
- Register exception handlers once on the shared API in `api/urls.py`. Do not
  import a per-endpoint `handle_exceptions` decorator; it does not exist.
- Require `JWTAuth` on private controllers and declare public operations with
  `auth=None`. Give staff-only operations `IsAdminUser`.
- Review every new anonymous operation before you make it public. After the
  review, add its `(method, path)` to `PUBLIC_OPERATIONS` in
  `core/tests/test_route_auth.py`. Do not add routes to make the test pass:
  the test fails on purpose when an operation is public by mistake.
- Put static URL paths before dynamic `/{id}` paths in each controller so
  dynamic paths do not shadow static operations.
- Do not hide a constraint in a `@field_validator` when `Field(...)`,
  `Literal`, or an `Enum` can express it. The frontend Zod schemas come from
  `docs/openapi/openapi.json`; run `just openapi` after any schema or route
  change and commit the file.
- Do not exempt an endpoint from CSRF to make a browser call work. Unsafe
  API methods need `X-CSRFToken` (`docs/COOKIE_AUTH.md`).

### Infrastructure

- Do not add a second `docker-compose.yml`. Add a service under a profile.
- Do not add a service that depends on `db` or `valkey` without adding your
  profile to that base service's `profiles` list.
- Do not use `grep -r`. Use `rg`, or the `just search` recipe.
- Do not use `pip` or `poetry`. Use `uv`.
- Do not add a dependency without an entry in `DEPENDENCIES.md`.
- Do not run `scripts/release.py` without `--dry-run` unless you intend to
  commit and tag. It pushes only with `--push`; unknown flags exit with an
  error, and `--help` prints usage.

### Task queues

- Import `shared_task` from `api.tasks`, not from Celery.
- Keep task definitions backend-neutral. Use `.delay()` and raise `.retry()`
  from the decorated task handle.
- Add a new task backend as an optional extra and a Compose profile. The loader
  must fail loud when the package is absent.

### Code organization

- Do not introduce an abstraction before there is a second real use case.
- Do not use `from module import *`. Explicit imports only.
- Do not let a file grow past its length cap. Split it.
- Do not comment out code. Delete it.

## 09 The gauntlet (quality gate)

Every change must survive these gates before merge. No exceptions. This is what
lets us trust generated code without reading every line.

| # | Gate | Tool | Catches |
|---|---|---|---|
| 1 | FORMAT | `ruff format --check` | Style drift |
| 2 | LINT | `ruff check` | Bugs, anti-patterns, dead code |
| 3 | TYPECHECK | `mypy` | Type errors, missing annotations |
| 4 | SECURITY | `bandit` | SQLi, XSS, hardcoded secrets |
| 5 | CONVENTIONS | `scripts/check_conventions.py` | DRF imports, raw `Schema`, decorator order, unscoped queries, redeclared fields, `Any`/bare `dict` schema fields without `# schema-ok:` |
| 6 | DEPENDENCIES | `scripts/check_dependencies.py` | `pyproject.toml` changed without a `DEPENDENCIES.md` entry |
| 7 | DRIFT | `scripts/check_version_drift.py` | Python, uv, Postgres, Valkey or hook tool versions that differ between `pyproject.toml`, `uv.lock`, Dockerfiles, Compose and `.pre-commit-config.yaml` |
| 8 | ARCHITECTURE | `scripts/check_architecture.py` | Layer violations, cross-app coupling |
| 9 | OPENAPI | `manage.py export_openapi --check` | `docs/openapi/openapi.json` out of date with the code |
| 10 | SCHEMA-PARITY | `scripts/check_schema_parity.py` | snake_case or untyped properties, required/nullable mismatches in the OpenAPI contract |
| 11 | FILELENGTH | `scripts/check_file_length.py` | Files over their cap |
| 12 | CROSS-STACK | `scripts/check_cross_stack.py` | Naming and schema parity (monorepo only) |
| 13 | TEST | `pytest --cov-fail-under=30` | Broken behaviour, coverage drop |
| 14 | CLI-TEST | `pytest cli/tests` | Broken `cli/` package |
| 15 | AI-DB | `scripts/test_ai_db.py` | Postgres-only tests (`core.ai` owner scoping, concurrent refresh) on a throwaway pgvector container; prints a skip reason when Docker is not running |
| 16 | DEPLOY-CHECK | `manage.py check --deploy` | Production config issues |

The full gauntlet adds MUTATION (`mutmut`), AUDIT and DOCKER (builds the
production image; skipped when Docker is not running). AUDIT runs
`scripts/audit_dependencies.py`: `pip-audit` on every package in `uv.lock`. It
always blocks. Put a known advisory with no fix in `pip-audit-allowlist.toml`
with a reason and an expiry date; an expired entry fails the gate.

There is no hosted CI. Every gate runs on your machine. `just pre-commit-install`
installs the git hooks; the pre-push hook runs `just gauntlet-quick` and the
audit. All hooks are `repo: local` and run tools through `uv run` (locked
tools) or a pinned `uvx`/`bunx`, so they cannot drift from the lockfile.

```bash
just gauntlet                 # every gate
just gauntlet-quick           # skip mutation, audit, docker (use this while working)
just gauntlet-ci              # every gate with a JSON report
just gauntlet-gate lint       # one gate by name
just pre-commit-install       # pre-commit, commit-msg and pre-push hooks
just check-conventions        # convention gate only
just check-cross-stack        # cross-stack gate only
just check-arch               # architecture gate only
just openapi                  # regenerate docs/openapi/openapi.json
just openapi-check            # OpenAPI staleness + schema parity gates
just check-drift              # version drift gate only
just audit                    # pip-audit on uv.lock (blocking)
just mutation-test            # mutation testing only
just security-scan            # bandit only
just security-full            # optional: bandit, audit, semgrep, SBOM, trivy
just test-django6             # manual: the suite on Django 6.0 (not supported yet)
```

`make -f Makefile.legacy gauntlet-quick` is the fallback if `just` is missing.

### Architecture rules the checker enforces

1. Layers flow Controllers to Services to Models. No reverse imports.
2. Models cannot import schemas, services, or controllers.
3. Cross-app communication goes through services, not controllers.
4. Migrations cannot import controllers, services, or schemas.

## 10 Definition of done

A task is done when all of these hold:

- [ ] The code implements the requirement, not just the happy path
- [ ] Tests for the change pass (`just test`)
- [ ] The gauntlet passes (`just gauntlet-quick`)
- [ ] No new linter warnings
- [ ] Architecture constraints respected
- [ ] Files are under their length cap
- [ ] Type hints on all public interfaces
- [ ] Commit message follows Conventional Commits (`type(scope): summary`)

Rules the gauntlet cannot fully enforce, and that you must follow yourself:

- Follow the testing policy below.
- No commented-out code, no `print()` in production code.
- No `# type: ignore`, `# nosec`, or `# noqa` without a written reason.
- Run `just gauntlet-quick` before declaring work complete.

### Testing policy

Write a test only for one of these:

- A bug fix: a regression test that fails before the fix and passes after.
- A changed public contract: a route, schema, status code, error shape, or
  setting that a client or operator depends on.
- A boundary or permission rule: auth, ownership scoping, limits, validation
  edges.

Do not write tests for wiring, getters, schema echo, default values, copied
constants, or mock calls. Do not copy a test that already exists in another
file. A test must assert on behavior (the response, the database state, the
raised error, the exact returned value), not on `mock.assert_called*`,
`is not None`, `isinstance` or `len(...) > 0`.

Create at most one new test file per change. Never add a test to reach a
coverage number. Prove a new feature by running it; a throwaway script does
not belong in `tests/`.

`just test` runs only the tests for the files you changed, without coverage,
and stops at the first failure. `just test-all` runs every test without
coverage. Coverage runs in `just gauntlet`. Two TTSR rules in `.omp/rules/`
(`ttsr-test-new-file.md`, `ttsr-test-assertions.md`) enforce this policy.

## 11 Constraint tools

The `scripts/` checkers are deterministic gates: same input, same result, exit 0
on pass and 1 on fail. They are small on purpose and an agent can extend them.

To add a gate:

1. Write a script in `scripts/` that exits 0 on pass and 1 on fail.
2. Keep it under its length cap.
3. Register it in `scripts/gauntlet.py` as a `_gate_*` method.
4. Add a recipe in the `justfile`.
5. Document it in the gates table in section 09.

## 12 Where the guidance lives

| Path | Purpose |
|---|---|
| `AGENTS.md` | This file. Canonical, harness-agnostic guidance. |
| `SKILLS.md` | Index of `.agents/skills/`. |
| `.agents/skills/` | Task-specific Agent Skills, loaded on demand. |
| `.omp/` | oh-my-pi harness config: `APPEND_SYSTEM.md`, `rules/`, `skills/`. |
| `.context/` | Longer-form reference: conventions, anti-patterns, examples. |
| `docs/` | Architecture, migration, realtime, constraint-tool notes. |

`CLAUDE.md` is gitignored and not part of the repository. Do not add references
to it, and do not rely on it. Anything that belongs in shared guidance goes in
this file.

## When to add to this section

When you reject an implementation choice in review, add the lesson here before
the next session. Format: what not to do, what to do instead, and why. One line
per rule, no paragraphs.

## Reference library

For agent instruction patterns from leading open-source projects, see
https://ossrules.md/llms.txt.

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

### Decisions app

- Do not rename `noul` to `null`. `noul` is Laya's own question-type name; the
  engine rejects other spellings.
- Do not silently fall back from laya to jev. Fail loud with the install hint.
- Do not test with the real provider. Use `FakeProvider`.
- Do not load a model or touch the network in a unit test.

### Infrastructure

- Do not add a second `docker-compose.yml`. Add a service under a profile.
- Do not add a service that depends on `db` or `valkey` without adding your
  profile to that base service's `profiles` list.
- Do not use `grep -r`. Use `rg`, or the `just search` recipe.
- Do not use `pip` or `poetry`. Use `uv`.
- Do not add a dependency without an entry in `DEPENDENCIES.md`.
- Do not run `scripts/release.py` without `--dry-run` unless you intend to
  commit, tag, and push.

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
| 5 | CONVENTIONS | `scripts/check_conventions.py` | DRF imports, raw `Schema`, decorator order, unscoped queries, redeclared fields |
| 6 | DEPENDENCIES | `scripts/check_dependencies.py` | `pyproject.toml` changed without a `DEPENDENCIES.md` entry |
| 7 | ARCHITECTURE | `scripts/check_architecture.py` | Layer violations, cross-app coupling |
| 8 | FILELENGTH | `scripts/check_file_length.py` | Files over their cap |
| 9 | CROSS-STACK | `scripts/check_cross_stack.py` | Naming and schema parity (monorepo only) |
| 10 | TEST | `pytest --cov-fail-under=30` | Broken behaviour, coverage drop |
| 11 | DEPLOY-CHECK | `manage.py check --deploy` | Production config issues |

The full gauntlet adds MUTATION (`mutmut`) and AUDIT (`pip-audit`).

```bash
just gauntlet                 # every gate
just gauntlet-quick           # skip mutation + audit (use this while working)
just gauntlet-ci              # CI mode with a JSON report
just gauntlet-gate lint       # one gate by name
just check-conventions        # convention gate only
just check-cross-stack        # cross-stack gate only
just check-arch               # architecture gate only
just mutation-test            # mutation testing only
just security-scan            # bandit only
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
- [ ] Tests exist and pass (`just test`)
- [ ] The gauntlet passes (`just gauntlet-quick`)
- [ ] No new linter warnings
- [ ] Architecture constraints respected
- [ ] Files are under their length cap
- [ ] Type hints on all public interfaces
- [ ] Commit message follows Conventional Commits (`type(scope): summary`)

Rules the gauntlet cannot fully enforce, and that you must follow yourself:

- Every new feature ships tests; every bug fix ships a regression test.
- No commented-out code, no `print()` in production code.
- No `# type: ignore`, `# nosec`, or `# noqa` without a written reason.
- Run `just gauntlet-quick` before declaring work complete.

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

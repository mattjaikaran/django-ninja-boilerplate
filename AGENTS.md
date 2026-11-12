# AGENTS.md

Canonical guidance for every agent and harness. Read it before a non-trivial
change; the nearest `AGENTS.md` to the file you edit wins. Skills live in
`.agents/skills/` (index: `SKILLS.md`); reference material in `docs/`.
`CLAUDE.md` is one import line and holds no rules.

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
  Local Postgres 17 with pgvector; tests use SQLite unless `TEST_DB=postgres`,
  so any pytest run gives the same result on every machine.
- Start with `just doctor`: it checks tools, Docker, `.env`, secrets, the
  venv, hooks, worktrees, ports, services, migrations and OpenAPI, repairs
  what is safe (`--check` diagnoses only), then run `just agent-status`.
- `.env` targets host services (`DB_HOST=127.0.0.1`), `.env.development` the
  Compose `db` service; `just doctor` warns when they disagree.
- Ports: django 8000, mcp 8001, mailhog 8025, centrifugo 8800, flower 5555;
  Compose Postgres 5433, Valkey 6380. `just dev` moves a busy port and prints
  it (`just check-ports` previews); dev binds `127.0.0.1` (`DEV_BIND_ADDRESS`).
- Preview secrets with `python3 scripts/env_secrets.py fill --dry-run` before
  `just setup-env`.

## 08 Code standards

The full rules: the `django-ninja-dev` skill
(`.agents/skills/django-ninja-dev/references/code-rules.md`). Lookup tables:
`.omp/rules/backend-conventions.md`. Wrong vs. right code:
`.omp/rules/django-ninja-anti-patterns.md`. Reference app: `todos/` (copy
`todo_controller.py`, not its variants); start every new app with the
generator (`generate_feature api_endpoint`, skill `django-ninja-dev`).

Never, even where a gate cannot catch it:

- DRF, `ninja.Router`, a `views.py`, or an `api/` package inside an app.
- A raw `ninja.Schema` or `ModelSchema`, a redeclared base-model field, or
  business logic in a controller.
- ORM access in a controller; an unscoped `Model.objects.all()` holding user
  data; `.raw()` or `.extra()`.
- A merge migration, an edit to a migration on `main`, a
  `# safe-migrations: ignore` comment, or a fallback that hides invalid state.
- A static path after a `/{id}` handler, a CSRF exemption for a browser call,
  or an anonymous route missing from `PUBLIC_OPERATIONS`.
- `pip`, `npm`, `yarn`, `grep -r`, or an abstraction before a second real use.
- A new dependency without a `DEPENDENCIES.md` entry.
- A file over its length cap, commented-out code, a bare `print()` or a
  `# type: ignore`/`# noqa`/`# nosec` without a reason.

## 09 The gauntlet (quality gate)

Every change passes `just gauntlet-quick`; `just gauntlet` runs every gate
before a release. CI runs the same gates, and branch protection requires the
one `CI OK` check. The gate list, the full-run extras, the CI jobs and how to
add a gate: `docs/CONSTRAINT_TOOLS.md`. Run one gate with `just gauntlet-gate
<name>`, and `just openapi-check` for OPENAPI + SCHEMA-PARITY alone.

## 10 Definition of done

- [ ] The requirement works, not just the happy path
- [ ] `just test` and `just gauntlet-quick` pass
- [ ] User-visible changes update `docs/product/` and its Playwright tags
- [ ] A ticket's PR sets `status: done` in its ticket file
- [ ] No new linter warnings; architecture rules and length caps hold
- [ ] Type hints on all public interfaces
- [ ] Conventional Commits message (`type(scope): summary`)

Also (not gate-enforced): no commented-out code or `print()` in production
code; no `# type: ignore`, `# nosec` or `# noqa` without a reason.

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
can extend. Adding one: `docs/CONSTRAINT_TOOLS.md`.

## 12 Where the guidance lives

| Path | Purpose |
|---|---|
| `AGENTS.md` | Canonical rules (this file) |
| `SKILLS.md` | Index of `.agents/skills/` (loaded on demand) |
| `.omp/` | oh-my-pi: `APPEND_SYSTEM.md`, `rules/` (references, TTSR), `skills/` |
| `docs/` | Architecture, migration, realtime, constraint tools, agent handoff |
| `docs/product/`, `docs/tickets/` | Features, journeys and waves (section 13); worker tickets (section 14) |
| `tasks/specs/` | agent-run specs, the canonical unattended queue (section 14) |

No nested `AGENTS.md` exists; add one only for a package with its own
commands or rules.

## 13 Features, journeys and e2e tests

`docs/product/FEATURES.md` (features), the journey specs in
`docs/product/journeys/` (stories and steps) and one Playwright test per
journey in the frontend `e2e/`, tagged `@J-NNN` with `J-NNN-S<n>: ...`
steps, must agree.

- A checked feature or a `done` journey means a passing Playwright test,
  never "the code exists". Build the backend first: frontend work starts only
  when the journey's backend smoke test passes on `main`.
- A failing journey test is a known issue: set `building`, name a ticket in
  `known_issues`, and fix it before closing the ticket.
- `just check-journeys` (JOURNEYS gate) enforces this; `just sync-frontend
  <path>` checks a frontend's report and OpenAPI copy (`--check` exits 1 on
  drift). Format and sync loop: `docs/product/README.md`, `journey-sync`
  skill.

## 14 Work modes and handoff

- Solo mode: the maintainer and planner model may commit to `main`.
- agent-run (canonical for unattended work): the planner writes `READY`
  specs in `tasks/specs/S-*.md`; agent-run claims one, a small model
  implements it, `matt-assistant` opens the PR, `matt-reviewer` reviews, and
  the owner approves. A frontier model splits an `L` issue into `S` and `M`.
- Worker mode (fallback): a smaller model runs only `tier: small` tickets
  from `docs/tickets/`, edits only the files its ticket lists, never pushes
  to `main`, and opens a PR from the bot account. `just worker-once`
  (`--dry-run` previews) runs one iteration.
- Keep both queues full of work that needs no design decisions; `just tickets
  check` blocks collisions. Never run both queues on one repository at once.
- Roles and overnight loop: `docs/AGENT_HANDOFF.md`. Spec format:
  `tasks/specs/README.md`. Skills: `ticket-planner`, `ticket-worker`.

## When to add to this section

When you reject an implementation choice in review, add the lesson here before
the next session. Format: what not to do, what to do instead, and why. One line
per rule, no paragraphs.

- Do not let a smoke sweep accept 400 or 404 on a parameterless GET (it hid 12 shadowed todo routes and 3 audit routes); fail on any status of 400 or higher except 403 for regular users, because a list route has no input to reject.
- Do not mark status with a colored card edge or another accent (side or top bar, tinted card, glow): the owner rejected it as template-looking. Use one neutral 1px border and show status with the existing badge or a small dot.

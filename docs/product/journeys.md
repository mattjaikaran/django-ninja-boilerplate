# User stories and journeys

This file is the plan for the product: the personas, the user stories, the
journeys that prove them, the backend surface each journey needs, the backend
test that proves that surface, and the Playwright test that will prove the
journey end to end.

`FEATURES.md` and `journeys/J-NNN-slug.md` remain the source of truth for the
JOURNEYS gate. This file adds the delivery order: build the backend first,
then the frontend, then the Playwright test. Keep the three in step, as
[README.md](README.md) describes.

Only two layers prove a journey: its backend smoke test and its Playwright
test. Contract and permission tests guard API boundaries; they do not prove
a journey. Do not add unit, model or mock tests.

## Build the backend first

A journey ships in waves, and the waves run in order:

| Wave | Work | Exit condition |
|------|------|----------------|
| W1 | Backend surface: models, services, controllers, schemas, migrations, OpenAPI | A smoke test calls the journey's endpoints in order and passes on `main` |
| W2 | Frontend screens for the journey | The screens call the real endpoints and follow the journey acceptance lines |
| W3 | Playwright test for the journey | One test tagged `@J-NNN` passes and each step has a `J-NNN-S<n>:` title |
| W4 | Optional apps and scale work | Flag-gated apps, satellite services and load tests, each behind its trigger in [../ARCHITECTURE.md](../ARCHITECTURE.md) |

Never start W2 for a journey whose W1 smoke test is missing or failing. Never
check a feature `[x]` or set a journey to `done` before W3 passes.

Every issue names one wave and one size. Sizes are in
[CONTRIBUTING.md](../../.github/CONTRIBUTING.md#sizes).

## Personas

| Persona | Plan | Goal |
|---------|------|------|
| Visitor | None | Create an account or sign in |
| Signed-in user | Free | Manage todos and see updates |
| Developer | Free | Call the API from a script with an API key |
| Team admin | Team | Manage an organization and its members |
| Customer | Paid | Subscribe, manage billing and upload files |
| Integrator | Any | Receive outbound webhooks |
| Staff | Staff | Operate the admin panel, users, audit, tasks and health |

## User stories

| ID | As a | I want to | So that | Features |
|----|------|-----------|---------|----------|
| US-01 | visitor | create an account, sign in, stay signed in and sign out | I can save my work | F-001, F-002, F-003, F-004 |
| US-02 | visitor | sign in without a password and reset a forgotten password | I can reach my account without one | F-005, F-006 |
| US-03 | visitor | verify my email and add a second factor | my account is harder to take over | F-007, F-008 |
| US-04 | developer | create, list, rotate and revoke API keys | my scripts can call the API and I can replace a leaked key | F-009 |
| US-05 | signed-in user | create, edit, complete, delete, search and filter todos | my list holds what I still have to do | F-010, F-011 |
| US-06 | signed-in user | receive updates without reloading | I see changes while I work | F-012 |
| US-07 | team admin | manage an organization and its members | my team shares one workspace | F-013 |
| US-08 | user | receive in-app and email notifications | I hear about what needs me | F-014 |
| US-09 | customer | subscribe, manage and cancel a plan | I control what I pay for | F-015 |
| US-10 | user | upload files with presigned URLs | I can attach large files without proxying them | F-016 |
| US-11 | integrator | receive signed outbound webhooks | my system reacts to changes | F-017 |
| US-12 | staff | use the admin panel for users, audit, tasks and health | I can operate the service | F-018 |

A story without a journey is backlog. Do not mark it done, and do not add
Playwright tests for it.

## Journeys

| ID | Journey | Stories | Backend surface (build first) | Backend smoke test | Planned Playwright test |
|----|---------|---------|-------------------------------|--------------------|-------------------------|
| J-001 | Sign up and sign in | US-01 | `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/refresh`, `POST /api/auth/logout` | `tests/smoke/test_smoke.py::test_auth_token_pair`; `core/tests/test_token_refresh.py::TestLoginRefreshFlow::test_login_tokens_rotate_and_logout`; `core/tests/test_auth.py` for the boundary rules | `e2e/j001-auth.spec.ts` in the frontend repo |
| J-002 | Manage todos | US-05 | `GET/POST /api/todos/`, `GET/PUT/DELETE /api/todos/{todo_id}`, `GET /api/todos/search`, `GET /api/todos/completed`, `GET /api/todos/pending` | `tests/smoke/test_smoke.py::test_todos_basic_list`; `todos/tests/test_todo.py::TestTodoAPI`; `tests/smoke/test_smoke.py::test_get_route_sweep` for search and filters | `e2e/j002-todos.spec.ts` in the frontend repo |
| J-003 | Manage API keys | US-04 | `POST/GET /api/api-keys/`, `POST /api/api-keys/{key_id}/rotate`, `DELETE /api/api-keys/{key_id}` | `tests/smoke/test_j003_api_keys.py` | `e2e/j003-api-keys.spec.ts` in the frontend repo |

A journey row is valid only when `journeys/J-NNN-slug.md` exists and the gate
reports no error. Add the journey file and this row in the same change.

## Backend smoke tests

A journey's backend proof is a smoke test. When no app test already proves
the surface, write `tests/smoke/test_jNNN_<name>.py`, where `NNN` is the
journey number. It calls the journey's endpoints in order and checks the
status code and the response shape, against a real database. When app tests
already prove the surface, name those tests in the table instead of copying
them, as [AGENTS.md](../../AGENTS.md#10-definition-of-done) requires.

Smoke tests follow the policy in [AGENTS.md](../../AGENTS.md#10-definition-of-done):
they catch a consumer-visible break, not a wiring or mock detail. Use the
`smoke_client`, `smoke_user` and `smoke_auth_headers` fixtures in
`tests/smoke/conftest.py`.

## Adding a journey

1. Add the user story to the table if it is new.
2. Ship the W1 backend surface with its smoke test, and run `just openapi`.
3. Write `journeys/J-NNN-slug.md` with steps, stories, features and
   acceptance lines, and add the row above.
4. Ship W2 in the frontend repo, then the tagged W3 Playwright test.
5. Run `just check-journeys` and fix every error before you set the journey
   to `done`.

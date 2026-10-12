---
id: T-008
title: Prune model tests from todos/tests/test_todo.py
status: ready
tier: small
depends_on: []
owns:
  - todos/tests/test_todo.py
shared: []
journeys: []
features: []
branch: agent/T-008-prune-todo-model-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 3 test functions from `todos/tests/test_todo.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** Every `TestTodoAPI` test stays. They cover the CRUD contract and the ownership boundary (`test_cannot_access_others_todo`, `test_list_user_todos`).

Read only `todos/tests/test_todo.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestTodoModel::test_create_todo`|Tests the factory and model defaults.|
|`TestTodoModel::test_todo_str`|`__str__` test.|
|`TestTodoModel::test_todo_ordering`|Model `Meta.ordering` test.|

## Change

Line numbers match `todos/tests/test_todo.py` when this ticket was written. If the lines moved, find each test by name.

1. In `todos/tests/test_todo.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestTodoModel` (lines 33-63). Every test in it goes: `test_create_todo`, `test_todo_str`, `test_todo_ordering`.
2. Delete the `todo` fixture (lines 17-20, from `@pytest.fixture` through `return TodoFactory(user=user)`). Only the deleted `test_todo_str` uses it.
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format todos/tests/test_todo.py`. Do not run it on other files.

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.
- Do not change non-test code.
- Do not rewrite, rename, or reorder the kept tests.
- Do not add tests.
- Do not delete a test, fixture, import, or comment that this ticket does not name.

## Verify

```bash
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest todos/tests/test_todo.py -q --no-cov -p no:cacheprovider
```

Expected: `6 passed` (no failures, no errors).

```bash
uv run ruff check todos/tests/test_todo.py
uv run ruff format --check todos/tests/test_todo.py
grep -cE '^ *def test_' todos/tests/test_todo.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `6`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 3 tests in the table under Context are gone, and 6 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

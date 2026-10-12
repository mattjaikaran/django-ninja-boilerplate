---
id: T-009
title: Prune duplicate tests from todos/tests/test_pagination.py
status: ready
tier: small
depends_on: []
owns:
  - todos/tests/test_pagination.py
shared: []
journeys: []
features: []
branch: agent/T-009-prune-todo-pagination-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 3 test functions from `todos/tests/test_pagination.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The envelope, page, page size and maximum page size tests stay. They are the pagination contract.

Read only `todos/tests/test_pagination.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestPaginationEnvelope::test_empty_results`|Duplicate of `test_envelope_shape` (same keys, empty list).|
|`TestPaginationUserScope::test_only_current_users_todos`|Duplicate of `todos/tests/test_todo.py::TestTodoAPI::test_list_user_todos`.|
|`TestPaginationOpenAPI::test_envelope_declared_in_schema`|Duplicate of `tests/contract/test_openapi_contract.py::TestOpenAPIContract::test_openapi_declares_page_envelope`, which covers `/api/todos/`.|

## Change

Line numbers match `todos/tests/test_pagination.py` when this ticket was written. If the lines moved, find each test by name.

1. In `todos/tests/test_pagination.py`, delete these blocks. Include the decorators above each block.
   - `TestPaginationEnvelope::test_empty_results` (lines 64-70).
   - The whole class `TestPaginationUserScope` (lines 73-83). Every test in it goes: `test_only_current_users_todos`.
   - The whole class `TestPaginationOpenAPI` (lines 86-100). Every test in it goes: `test_envelope_declared_in_schema`.
2. Delete the line `from core.tests.factories import UserFactory` (line 9).
3. Replace the module docstring (lines 1-4) with:

   ```python
   """Pagination tests: prove the todo list returns the framework pagination
   envelope ({count, next, previous, results}) with page/page_size controls.
   """
   ```

4. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format todos/tests/test_pagination.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest todos/tests/test_pagination.py -q --no-cov -p no:cacheprovider
```

Expected: `5 passed` (no failures, no errors).

```bash
uv run ruff check todos/tests/test_pagination.py
uv run ruff format --check todos/tests/test_pagination.py
grep -cE '^ *def test_' todos/tests/test_pagination.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `5`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 3 tests in the table under Context are gone, and 5 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

---
id: T-016
title: Prune a duplicate test from tests/smoke/test_task_contract.py
status: done
tier: small
depends_on: []
owns:
  - tests/smoke/test_task_contract.py
shared: []
journeys: []
features: []
branch: agent/T-016-prune-task-contract-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 1 test function from `tests/smoke/test_task_contract.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** Every other test stays. They are the contract for the backend-neutral task facade that every task backend must honor.

Read only `tests/smoke/test_task_contract.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`test_retry_signal_keeps_exception_and_payload`|Attribute echo of `TaskRetry`; `test_each_backend_exposes_uniform_contract` asserts the same fields.|

## Change

Line numbers match `tests/smoke/test_task_contract.py` when this ticket was written. If the lines moved, find each test by name.

1. In `tests/smoke/test_task_contract.py`, delete these blocks. Include the decorators above each block.
   - `test_retry_signal_keeps_exception_and_payload` (lines 140-147).
2. In the `api.tasks.contract` import block (lines 14-21), delete the line `    TaskRetry,` (line 18). Keep the other names.
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format tests/smoke/test_task_contract.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest tests/smoke/test_task_contract.py -q --no-cov -p no:cacheprovider
```

Expected: `13 passed` (no failures, no errors).

```bash
uv run ruff check tests/smoke/test_task_contract.py
uv run ruff format --check tests/smoke/test_task_contract.py
grep -cE '^ *def test_' tests/smoke/test_task_contract.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `9`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 1 test in the table under Context are gone, and 9 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

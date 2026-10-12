---
id: T-006
title: Prune mock-assert tests from core/tests/test_tracing_startup.py
status: done
tier: small
depends_on: []
owns:
  - core/tests/test_tracing_startup.py
shared: []
journeys: []
features: []
branch: agent/T-006-prune-tracing-startup-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 2 test functions from `core/tests/test_tracing_startup.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** `test_enabled_without_packages_fails_loud` stays. It guards that production fails at startup when tracing is on but the packages are missing.

Read only `core/tests/test_tracing_startup.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`test_disabled_does_not_start_tracing`|Replaces collaborators with fakes and asserts on the recorded calls.|
|`test_enabled_starts_and_instruments`|Replaces collaborators with fakes and asserts on the recorded calls.|

## Change

Line numbers match `core/tests/test_tracing_startup.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_tracing_startup.py`, delete these blocks. Include the decorators above each block.
   - `test_disabled_does_not_start_tracing` (lines 24-27).
   - `test_enabled_starts_and_instruments` (lines 30-33).
2. Delete the `calls` fixture (lines 9-21, from `@pytest.fixture` through `return seen`). Only the two deleted tests use it.
3. Replace the module docstring (line 1) with:

   ```python
   """CoreConfig fails loud when OTEL_ENABLED is true but tracing cannot start."""
   ```

4. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_tracing_startup.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_tracing_startup.py -q --no-cov -p no:cacheprovider
```

Expected: `1 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_tracing_startup.py
uv run ruff format --check core/tests/test_tracing_startup.py
grep -cE '^ *def test_' core/tests/test_tracing_startup.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `1`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 2 tests in the table under Context are gone, and 1 test function remains.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

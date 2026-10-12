---
id: T-004
title: Prune dashboard unit tests from test_observability_admin.py
status: ready
tier: small
depends_on: []
owns:
  - core/tests/test_observability_admin.py
shared: []
journeys: []
features: []
branch: agent/T-004-prune-observability-admin-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 2 test functions from `core/tests/test_observability_admin.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The four admin page tests stay. They guard the staff-only redirect and that each page renders.

Read only `core/tests/test_observability_admin.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestDashboardQuickLinks::test_flower_link_hidden_by_default`|Settings-default unit test of `dashboard_callback`.|
|`TestDashboardQuickLinks::test_flower_link_shown_when_configured`|Settings unit test of `dashboard_callback`; no security impact.|

## Change

Line numbers match `core/tests/test_observability_admin.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_observability_admin.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestDashboardQuickLinks` (lines 49-66). Every test in it goes: `test_flower_link_hidden_by_default`, `test_flower_link_shown_when_configured`.
2. Delete the line `from core.admin.dashboard import dashboard_callback` (line 12).
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_observability_admin.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_observability_admin.py -q --no-cov -p no:cacheprovider
```

Expected: `4 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_observability_admin.py
uv run ruff format --check core/tests/test_observability_admin.py
grep -cE '^ *def test_' core/tests/test_observability_admin.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `4`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 2 tests in the table under Context are gone, and 4 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

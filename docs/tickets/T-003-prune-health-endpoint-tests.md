---
id: T-003
title: Prune a duplicate test from core/tests/test_health_endpoints.py
status: done
tier: small
depends_on: []
owns:
  - core/tests/test_health_endpoints.py
shared: []
journeys: []
features: []
branch: agent/T-003-prune-health-endpoint-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 1 test function from `core/tests/test_health_endpoints.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** Every other test stays: they cover the staff gate (401/403), the 200/503 probe contract, and the OpenAPI declaration of 503.

Read only `core/tests/test_health_endpoints.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestLivenessAndBasic::test_liveness_is_public_and_alive`|Duplicate: `test_liveness_probes_nothing` makes the same anonymous request and the same assertions.|

## Change

Line numbers match `core/tests/test_health_endpoints.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_health_endpoints.py`, delete these blocks. Include the decorators above each block.
   - `TestLivenessAndBasic::test_liveness_is_public_and_alive` (lines 60-63).
2. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_health_endpoints.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_health_endpoints.py -q --no-cov -p no:cacheprovider
```

Expected: `17 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_health_endpoints.py
uv run ruff format --check core/tests/test_health_endpoints.py
grep -cE '^ *def test_' core/tests/test_health_endpoints.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `17`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 1 test in the table under Context are gone, and 17 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

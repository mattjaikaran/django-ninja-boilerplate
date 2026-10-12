---
id: T-005
title: Prune library and duplicate tests from core/tests/test_throttling.py
status: ready
tier: small
depends_on: []
owns:
  - core/tests/test_throttling.py
shared: []
journeys: []
features: []
branch: agent/T-005-prune-throttling-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 4 test functions from `core/tests/test_throttling.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The 429 `Retry-After` contract, the trusted-proxy spoof tests, and the unthrottled probe tests stay.

Read only `core/tests/test_throttling.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestBuckets::test_throttle_allows_up_to_limit_then_denies`|Tests the third-party `ninja_extra` throttle class, not project code.|
|`TestBuckets::test_throttle_wait_reports_retry_delay`|Tests the third-party `ninja_extra` throttle class, not project code.|
|`TestTrustedProxyChain::test_one_proxy_uses_last_xff_entry`|Duplicate of `test_attacker_prepended_xff_is_ignored` (same setup, same assertion).|
|`TestLoginLockoutIntact::test_lockout_after_five_failed_attempts`|Duplicate of `core/tests/test_auth.py::TestAuthAPI::test_account_lockout_blocks_even_the_right_password`, which is stricter.|

## Change

Line numbers match `core/tests/test_throttling.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_throttling.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestBuckets` (lines 45-64). Every test in it goes: `test_throttle_allows_up_to_limit_then_denies`, `test_throttle_wait_reports_retry_delay`.
   - `TestTrustedProxyChain::test_one_proxy_uses_last_xff_entry` (lines 101-105).
   - The whole class `TestLoginLockoutIntact` (lines 151-165). Every test in it goes: `test_lockout_after_five_failed_attempts`.
2. Delete the section comment block above `TestBuckets` (lines 40-42, the `# Buckets` banner) and the section comment block above `TestLoginLockoutIntact` (lines 146-148, the `# Intact brute-force login lockout` banner).
3. Replace the module docstring (lines 1-6) with:

   ```python
   """Throttling behaviour tests.

   Covers 429 retry metadata, trusted/untrusted proxy chain behaviour, spoof
   resistance, and unthrottled probes.
   """
   ```

4. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_throttling.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_throttling.py -q --no-cov -p no:cacheprovider
```

Expected: `8 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_throttling.py
uv run ruff format --check core/tests/test_throttling.py
grep -cE '^ *def test_' core/tests/test_throttling.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `8`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 4 tests in the table under Context are gone, and 8 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

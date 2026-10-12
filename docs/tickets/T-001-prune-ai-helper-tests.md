---
id: T-001
title: Prune helper unit tests from core/tests/test_ai_helpers.py
status: ready
tier: small
depends_on: []
owns:
  - core/tests/test_ai_helpers.py
shared: []
journeys: []
features: []
branch: agent/T-001-prune-ai-helper-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 3 test functions from `core/tests/test_ai_helpers.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The two owner-scoping tests stay. They guard that one user cannot read or walk into another user's documents.

Read only `core/tests/test_ai_helpers.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`test_rrf_ranks_a_key_found_by_both_rankings_first`|Unit test of the pure `reciprocal_rank_fusion` helper; not security logic.|
|`test_rrf_breaks_ties_by_first_appearance`|Unit test of the same helper (tie-break detail).|
|`test_cache_key_ignores_dict_order_but_not_content`|Unit test of the pure `prompt_cache_key` helper; not security logic.|

## Change

Line numbers match `core/tests/test_ai_helpers.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_ai_helpers.py`, delete these blocks. Include the decorators above each block.
   - `test_rrf_ranks_a_key_found_by_both_rankings_first` (lines 71-77).
   - `test_rrf_breaks_ties_by_first_appearance` (lines 80-82).
   - `test_cache_key_ignores_dict_order_but_not_content` (lines 85-94).
2. Replace the `core.ai.services` import block (lines 11-16) with:

   ```python
   from core.ai.services import hybrid_search, reachable
   ```

3. Replace the module docstring (line 1) with:

   ```python
   """Owner scoping for hybrid search and document-link graph walks."""
   ```

4. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_ai_helpers.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_ai_helpers.py -q --no-cov -p no:cacheprovider
```

Expected: `2 skipped` (no failures, no errors). Both kept tests need Postgres with pgvector, so they skip under the default SQLite test database. `scripts/test_ai_db.py` runs them on Postgres; do not change it.

```bash
uv run ruff check core/tests/test_ai_helpers.py
uv run ruff format --check core/tests/test_ai_helpers.py
grep -cE '^ *def test_' core/tests/test_ai_helpers.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `2`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 3 tests in the table under Context are gone, and 2 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

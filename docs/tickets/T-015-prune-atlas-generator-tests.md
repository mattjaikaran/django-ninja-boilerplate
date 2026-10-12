---
id: T-015
title: Prune generator unit tests from atlas/tests/test_atlas.py
status: done
tier: small
depends_on: []
owns:
  - atlas/tests/test_atlas.py
shared: []
journeys: []
features: []
branch: agent/T-015-prune-atlas-generator-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 3 test functions from `atlas/tests/test_atlas.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The generator structure and edge-integrity tests stay, and so do the staff-only admin view tests.

Read only `atlas/tests/test_atlas.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestAtlasGenerator::test_packets_are_serializable_json`|Covered by `TestAtlasAdminViews::test_staff_data_endpoint_returns_json`, which serializes the data.|
|`TestAtlasGenerator::test_layout_produces_painter_order`|Unit test of an internal layout detail.|
|`TestAtlasGenerator::test_children_blocks_exist_for_apps_with_components`|Schema echo of generator output.|

## Change

Line numbers match `atlas/tests/test_atlas.py` when this ticket was written. If the lines moved, find each test by name.

1. In `atlas/tests/test_atlas.py`, delete these blocks. Include the decorators above each block.
   - `TestAtlasGenerator::test_packets_are_serializable_json` (lines 45-50).
   - `TestAtlasGenerator::test_layout_produces_painter_order` (lines 52-60).
   - `TestAtlasGenerator::test_children_blocks_exist_for_apps_with_components` (lines 62-68).
2. Delete the line `import json` (line 11).
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format atlas/tests/test_atlas.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest atlas/tests/test_atlas.py -q --no-cov -p no:cacheprovider
```

Expected: `7 passed` (no failures, no errors).

```bash
uv run ruff check atlas/tests/test_atlas.py
uv run ruff format --check atlas/tests/test_atlas.py
grep -cE '^ *def test_' atlas/tests/test_atlas.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `7`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 3 tests in the table under Context are gone, and 7 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

---
id: T-014
title: Prune field-echo tests from test_organizations.py
status: draft  # parked: organizations is an optional app; the maintainer left it as is
tier: small
depends_on: []
owns:
  - organizations/tests/test_organizations.py
shared: []
journeys: []
features: []
branch: agent/T-014-prune-organization-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 2 test functions from `organizations/tests/test_organizations.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

The `organizations` app is commented out of `INSTALLED_APPS` in `api/settings/common.py`, so this file does not run in the default test suite and pytest cannot collect it. You verify this ticket with `ruff`, `py_compile` and a test count instead of a test run.

**Kept on purpose.** The membership, scoping and permission tests stay: owner membership, slug de-duplication, org listing per user, invite permission (403), duplicate invite (409), and the leave rules.

Read only `organizations/tests/test_organizations.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestCreateOrganization::test_creates_organization`|Field echo of the create call.|
|`TestCreateOrganization::test_auto_generates_slug_from_name`|Covered by `test_slug_deduplication`, which asserts the generated slug.|

## Change

Line numbers match `organizations/tests/test_organizations.py` when this ticket was written. If the lines moved, find each test by name.

1. In `organizations/tests/test_organizations.py`, delete these blocks. Include the decorators above each block.
   - `TestCreateOrganization::test_creates_organization` (lines 42-49).
   - `TestCreateOrganization::test_auto_generates_slug_from_name` (lines 59-63).
2. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format organizations/tests/test_organizations.py`. Do not run it on other files.

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.
- Do not change non-test code.
- Do not rewrite, rename, or reorder the kept tests.
- Do not add tests.
- Do not delete a test, fixture, import, or comment that this ticket does not name.
- Do not change `api/settings/` to install the `organizations` app.

## Verify

```bash
uv run python -m py_compile organizations/tests/test_organizations.py
```

Expected: no output, exit code 0.

```bash
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest organizations/tests/test_organizations.py -q --no-cov -p no:cacheprovider
```

Expected: `1 error`, with `RuntimeError: Model class organizations.models.organization.Organization doesn't declare an explicit app_label and isn't in an application in INSTALLED_APPS.` Exit code 2. This is the same result as before the change. Any other error means the edit broke the file.

```bash
uv run ruff check organizations/tests/test_organizations.py
uv run ruff format --check organizations/tests/test_organizations.py
grep -cE '^ *def test_' organizations/tests/test_organizations.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `11`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 2 tests in the table under Context are gone, and 11 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

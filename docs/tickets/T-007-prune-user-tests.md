---
id: T-007
title: Prune model and duplicate tests from core/tests/test_user.py
status: ready
tier: small
depends_on: []
owns:
  - core/tests/test_user.py
shared: []
journeys: []
features: []
branch: agent/T-007-prune-user-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 9 test functions from `core/tests/test_user.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** `TestUserAPI::test_get_user`, `test_update_user` and `test_delete_user` stay. They are the only success-path tests for the staff user admin endpoints.

Read only `core/tests/test_user.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestUserModel::test_create_user`|Tests the factory and model defaults.|
|`TestUserModel::test_create_superuser`|Tests the factory.|
|`TestUserModel::test_user_str`|`__str__` test.|
|`TestUserModel::test_user_full_name`|Model property unit test.|
|`TestUserModel::test_duplicate_email`|Model constraint test; signup uniqueness is covered by `test_auth.py::TestAuthAPI::test_signup_answer_does_not_reveal_existing_accounts`.|
|`TestUserModel::test_duplicate_username`|Model constraint test; covered by the same signup test.|
|`TestUserModel::test_email_required`|Model manager unit test.|
|`TestUserAPI::test_signup`|Duplicate of `test_auth.py::TestAuthAPI::test_signup_answer_does_not_reveal_existing_accounts`.|
|`TestUserAPI::test_list_users`|Duplicate of `core/tests/test_list_pagination.py::TestAdminListPagination::test_users_list_has_page_envelope_and_distinct_pages`.|

## Change

Line numbers match `core/tests/test_user.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_user.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestUserModel` (lines 22-55). Every test in it goes: `test_create_user`, `test_create_superuser`, `test_user_str`, `test_user_full_name`, `test_duplicate_email`, `test_duplicate_username`, `test_email_required`.
   - `TestUserAPI::test_signup` (lines 75-87).
   - `TestUserAPI::test_list_users` (lines 94-99).
2. Delete the line `from django.db import IntegrityError` (line 3).
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_user.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_user.py -q --no-cov -p no:cacheprovider
```

Expected: `3 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_user.py
uv run ruff format --check core/tests/test_user.py
grep -cE '^ *def test_' core/tests/test_user.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `3`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 9 tests in the table under Context are gone, and 3 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

---
id: T-012
title: Prune model and duplicate tests from test_notifications.py
status: ready
tier: small
depends_on: []
owns:
  - notifications/tests/test_notifications.py
shared: []
journeys: []
features: []
branch: agent/T-012-prune-notification-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 10 test functions from `notifications/tests/test_notifications.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

The `notifications` app is commented out of `INSTALLED_APPS` in `api/settings/common.py`, so this file does not run in the default test suite and pytest cannot collect it. You verify this ticket with `ruff`, `py_compile` and a test count instead of a test run.

**Kept on purpose.** Every `TestNotificationAPI` test stays, and so does `TestNotificationService::test_mark_all_read_only_for_user`, the only test that proves "mark all read" does not touch another user's notifications.

Read only `notifications/tests/test_notifications.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestNotificationModel::test_create_notification`|Model field test.|
|`TestNotificationModel::test_mark_read`|Model method unit test; covered by `TestNotificationAPI::test_mark_single_read`.|
|`TestNotificationModel::test_str`|`__str__` test.|
|`TestNotificationModel::test_notify_convenience_function`|Unit test of a thin wrapper around `create_notification`.|
|`TestNotificationService::test_list_notifications`|Duplicate of `TestNotificationAPI::test_list_notifications`.|
|`TestNotificationService::test_list_notifications_unread_only`|Duplicate of `TestNotificationAPI::test_list_unread_only`.|
|`TestNotificationService::test_get_unread_count`|Duplicate of `TestNotificationAPI::test_get_unread_count`.|
|`TestNotificationService::test_mark_all_read`|Duplicate of `TestNotificationAPI::test_mark_all_read`.|
|`TestNotificationService::test_delete_notification`|Duplicate of `TestNotificationAPI::test_delete_notification`.|
|`TestNotificationService::test_get_notification_wrong_user`|Duplicate of `TestNotificationAPI::test_cannot_access_other_users_notification`.|

## Change

Line numbers match `notifications/tests/test_notifications.py` when this ticket was written. If the lines moved, find each test by name.

1. In `notifications/tests/test_notifications.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestNotificationModel` (lines 44-76). Every test in it goes: `test_create_notification`, `test_mark_read`, `test_str`, `test_notify_convenience_function`.
   - `TestNotificationService::test_list_notifications` (lines 81-85).
   - `TestNotificationService::test_list_notifications_unread_only` (lines 87-93).
   - `TestNotificationService::test_get_unread_count` (lines 95-98).
   - `TestNotificationService::test_mark_all_read` (lines 100-105).
   - `TestNotificationService::test_delete_notification` (lines 114-117).
   - `TestNotificationService::test_get_notification_wrong_user` (lines 119-123).
2. Replace the line `from notifications.services import NotificationService, notify` (line 6) with:

   ```python
   from notifications.services import NotificationService
   ```

3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format notifications/tests/test_notifications.py`. Do not run it on other files.

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.
- Do not change non-test code.
- Do not rewrite, rename, or reorder the kept tests.
- Do not add tests.
- Do not delete a test, fixture, import, or comment that this ticket does not name.
- Do not change `api/settings/` to install the `notifications` app.

## Verify

```bash
uv run python -m py_compile notifications/tests/test_notifications.py
```

Expected: no output, exit code 0.

```bash
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest notifications/tests/test_notifications.py -q --no-cov -p no:cacheprovider
```

Expected: `1 error`, with `RuntimeError: Model class notifications.models.notification.Notification doesn't declare an explicit app_label and isn't in an application in INSTALLED_APPS.` Exit code 2. This is the same result as before the change. Any other error means the edit broke the file.

```bash
uv run ruff check notifications/tests/test_notifications.py
uv run ruff format --check notifications/tests/test_notifications.py
grep -cE '^ *def test_' notifications/tests/test_notifications.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `8`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 10 tests in the table under Context are gone, and 8 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

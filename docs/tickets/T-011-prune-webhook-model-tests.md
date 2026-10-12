---
id: T-011
title: Prune model tests from webhooks/tests/test_webhooks.py
status: done
tier: small
depends_on: []
owns:
  - webhooks/tests/test_webhooks.py
shared: []
journeys: []
features: []
branch: agent/T-011-prune-webhook-model-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 5 test functions from `webhooks/tests/test_webhooks.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The API, ownership, dispatch and SSRF tests stay. The SSRF tests guard URL validation, IP pinning and the response size cap.

Read only `webhooks/tests/test_webhooks.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestWebhookModel::test_create_webhook`|Model field defaults test.|
|`TestWebhookModel::test_webhook_str`|`__str__` test.|
|`TestWebhookModel::test_webhook_delivery_is_successful`|Model property unit test.|
|`TestWebhookModel::test_webhook_delivery_not_successful_on_5xx`|Model property unit test.|
|`TestWebhookModel::test_webhook_delivery_not_successful_when_none`|Model property unit test.|

## Change

Line numbers match `webhooks/tests/test_webhooks.py` when this ticket was written. If the lines moved, find each test by name.

1. In `webhooks/tests/test_webhooks.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestWebhookModel` (lines 63-104). Every test in it goes: `test_create_webhook`, `test_webhook_str`, `test_webhook_delivery_is_successful`, `test_webhook_delivery_not_successful_on_5xx`, `test_webhook_delivery_not_successful_when_none`.
2. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format webhooks/tests/test_webhooks.py`. Do not run it on other files.

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
WEBHOOKS_ENABLED=true DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest webhooks/tests/test_webhooks.py -q --no-cov -p no:cacheprovider
```

Expected: `26 passed` (no failures, no errors). The `webhooks` app is optional, so the command sets `WEBHOOKS_ENABLED=true`. Without it, collection fails with `RuntimeError: Model class webhooks.models.webhook.Webhook doesn't declare an explicit app_label`.

```bash
uv run ruff check webhooks/tests/test_webhooks.py
uv run ruff format --check webhooks/tests/test_webhooks.py
grep -cE '^ *def test_' webhooks/tests/test_webhooks.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `19`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 5 tests in the table under Context are gone, and 19 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

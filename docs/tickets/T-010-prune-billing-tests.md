---
id: T-010
title: Prune model and mock-assert tests from billing/tests/test_billing.py
status: done
tier: small
depends_on: []
owns:
  - billing/tests/test_billing.py
shared: []
journeys: []
features: []
branch: agent/T-010-prune-billing-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 14 test functions from `billing/tests/test_billing.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The endpoint tests stay: anonymous plan listing, subscription 404/200/auth, checkout auth/400/404/success, the CSRF-exempt webhook route, and the invalid-signature rejection.

Read only `billing/tests/test_billing.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestPlanModel::test_is_free_false_for_paid_plan`|Model property unit test.|
|`TestPlanModel::test_is_free_true_for_zero_amount`|Model property unit test.|
|`TestPlanModel::test_str`|`__str__` test.|
|`TestPlanModel::test_active_filter`|Tests the Django ORM filter, not project code.|
|`TestPlanModel::test_stripe_price_id_unique_only_when_set`|Model constraint test.|
|`TestSubscriptionModel::test_is_active_when_active`|Model property unit test.|
|`TestSubscriptionModel::test_is_active_when_trialing`|Model property unit test.|
|`TestSubscriptionModel::test_not_active_when_canceled`|Model property unit test.|
|`TestSubscriptionModel::test_str`|`__str__` test.|
|`TestListPlansEndpoint::test_list_plans_returns_active_only`|Duplicate of `test_list_plans_no_auth_required`, which already asserts the inactive plan is absent.|
|`TestListPlansEndpoint::test_plan_schema_includes_is_free`|Schema echo.|
|`TestWebhookController::test_webhook_routes_checkout_completed`|Mocks Stripe and the service, asserts on the mock.|
|`TestWebhookController::test_webhook_routes_payment_failed`|Mocks Stripe and the service, asserts on the mock.|
|`TestWebhookController::test_webhook_routes_subscription_deleted`|Mocks Stripe and the service, asserts on the mock.|

## Change

Line numbers match `billing/tests/test_billing.py` when this ticket was written. If the lines moved, find each test by name.

1. In `billing/tests/test_billing.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestPlanModel` (lines 66-95). Every test in it goes: `test_is_free_false_for_paid_plan`, `test_is_free_true_for_zero_amount`, `test_str`, `test_active_filter`, `test_stripe_price_id_unique_only_when_set`.
   - The whole class `TestSubscriptionModel` (lines 98-115). Every test in it goes: `test_is_active_when_active`, `test_is_active_when_trialing`, `test_not_active_when_canceled`, `test_str`.
   - `TestListPlansEndpoint::test_list_plans_returns_active_only` (lines 130-135).
   - `TestListPlansEndpoint::test_plan_schema_includes_is_free` (lines 137-143).
   - `TestWebhookController::test_webhook_routes_checkout_completed` (lines 276-293).
   - `TestWebhookController::test_webhook_routes_payment_failed` (lines 295-312).
   - `TestWebhookController::test_webhook_routes_subscription_deleted` (lines 314-331).
2. Delete the line `from django.db import IntegrityError, transaction` (line 5).
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format billing/tests/test_billing.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest billing/tests/test_billing.py -q --no-cov -p no:cacheprovider
```

Expected: `10 passed` (no failures, no errors).

```bash
uv run ruff check billing/tests/test_billing.py
uv run ruff format --check billing/tests/test_billing.py
grep -cE '^ *def test_' billing/tests/test_billing.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `10`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 14 tests in the table under Context are gone, and 10 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

---
id: T-002
title: Prune mock-only tests from core/tests/test_centrifugo.py
status: ready
tier: small
depends_on: []
owns:
  - core/tests/test_centrifugo.py
shared: []
journeys: []
features: []
branch: agent/T-002-prune-centrifugo-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 15 test functions from `core/tests/test_centrifugo.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** `TestConnectionToken::test_token_expiration_default` stays. It guards the token lifetime (`CENTRIFUGO_TOKEN_TTL`), which no API test checks. The realtime token endpoints are covered by `core/tests/test_realtime_tokens.py`.

Read only `core/tests/test_centrifugo.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestConnectionToken::test_basic_token`|Duplicates `core/tests/test_realtime_tokens.py::TestRealtimeTokens::test_connection_token_carries_the_caller` (API-level).|
|`TestConnectionToken::test_token_with_info`|Unit test of an optional claim; no API caller depends on it.|
|`TestConnectionToken::test_token_expiration_custom`|Unit test of an optional argument.|
|`TestConnectionToken::test_user_id_coerced_to_string`|Covered by the API test, which compares `sub` to `str(user.id)`.|
|`TestSubscriptionToken::test_basic_token`|Duplicates `test_realtime_tokens.py::TestRealtimeTokens::test_own_notifications_channel_is_allowed` (API-level).|
|`TestSubscriptionToken::test_token_with_info`|Unit test of an optional claim.|
|`TestCentrifugoClient::test_publish`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_broadcast`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_subscribe`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_unsubscribe`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_disconnect`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_presence`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_history`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_http_error_raises`|Mocks `httpx.post` and asserts on the mock.|
|`TestCentrifugoClient::test_error_payload_raises`|Mocks `httpx.post` and asserts on the mock.|

## Change

Line numbers match `core/tests/test_centrifugo.py` when this ticket was written. If the lines moved, find each test by name.

1. In `core/tests/test_centrifugo.py`, delete these blocks. Include the decorators above each block.
   - `TestConnectionToken::test_basic_token` (lines 28-35).
   - `TestConnectionToken::test_token_with_info` (lines 37-42).
   - `TestConnectionToken::test_token_expiration_custom` (lines 52-57).
   - `TestConnectionToken::test_user_id_coerced_to_string` (lines 59-64).
   - The whole class `TestSubscriptionToken` (lines 67-88). Every test in it goes: `test_basic_token`, `test_token_with_info`.
   - The whole class `TestCentrifugoClient` (lines 91-226). Every test in it goes: `test_publish`, `test_broadcast`, `test_subscribe`, `test_unsubscribe`, `test_disconnect`, `test_presence`, `test_history`, `test_http_error_raises`, `test_error_payload_raises`.
2. Delete the line `from unittest.mock import MagicMock, patch` (line 4) and the line `import pytest` (line 7). Replace the `api.centrifugo` import block (lines 10-14) with:

   ```python
   from api.centrifugo import generate_connection_token
   ```

3. Replace the module docstring (line 1) with:

   ```python
   """Tests for the Centrifugo connection token expiry."""
   ```

4. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format core/tests/test_centrifugo.py`. Do not run it on other files.

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
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_centrifugo.py -q --no-cov -p no:cacheprovider
```

Expected: `1 passed` (no failures, no errors).

```bash
uv run ruff check core/tests/test_centrifugo.py
uv run ruff format --check core/tests/test_centrifugo.py
grep -cE '^ *def test_' core/tests/test_centrifugo.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `1`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 15 tests in the table under Context are gone, and 1 test function remains.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.

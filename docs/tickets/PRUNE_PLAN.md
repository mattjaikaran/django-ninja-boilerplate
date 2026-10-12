# Test prune plan

This plan applies the testing policy in `AGENTS.md` (section 10) to the
backend test files. Each file with at least one cut test has one ticket. The
tickets do not overlap in `owns`, so workers can take them in any order.

Counts are test functions. A parametrized test counts once. The plan skips
`tests/e2e/` (removed) and `journeys/` (new).

## Rules used

- **Keep:** smoke, auth, permission and ownership boundaries, token refresh
  and lockout, route and OpenAPI contract, SSRF and upload validation,
  settings probes that guard production config, regression tests for a known
  bug, and tests for tooling the maintainer runs (gauntlet, release,
  dependency gate, CLI).
- **Cut:** model field, property and `__str__` tests, tests that assert on a
  mock, settings-default tests, schema echo, unit tests of helpers that are
  not security logic, tests of third-party library behavior, and duplicates of
  another test.
- When two tests overlap, the API-level or stricter test stays.

## Plan

|File|Before|Keep|Cut|Ticket|Kept on purpose|
|---|---|---|---|---|---|
|`core/tests/test_ai_helpers.py`|5|2|3|T-001|Owner scoping for hybrid search and graph walks (Postgres only).|
|`core/tests/test_auth.py`|14|14|0|-|Signup enumeration, lockout (account, IP, admin, shared counters), passwordless OTP.|
|`core/tests/test_centrifugo.py`|16|1|15|T-002|Token TTL check; realtime endpoints are covered in `test_realtime_tokens.py`.|
|`core/tests/test_exceptions.py`|3|3|0|-|Error status contract and the safe 500 body (no exception leak).|
|`core/tests/test_graphql_generator.py`|2|2|0|-|Regression tests for generator output paths.|
|`core/tests/test_health_endpoints.py`|18|17|1|T-003|Staff gate, 200/503 probe contract, OpenAPI 503 declarations.|
|`core/tests/test_list_pagination.py`|3|3|0|-|Staff list pagination contract.|
|`core/tests/test_observability_admin.py`|6|4|2|T-004|Staff-only admin pages.|
|`core/tests/test_packaging.py`|1|1|0|-|Deploy safety: every local app ships in the wheel.|
|`core/tests/test_realtime_tokens.py`|3|3|0|-|Realtime token auth and channel ownership.|
|`core/tests/test_route_auth.py`|13|13|0|-|401/403 route matrix and OpenAPI security allowlist.|
|`core/tests/test_throttling.py`|12|8|4|T-005|429 `Retry-After` contract, proxy spoof resistance, unthrottled probes.|
|`core/tests/test_token_refresh.py`|19|19|0|-|Refresh rotation, reuse revocation, logout, pruning, signing key separation.|
|`core/tests/test_tracing_startup.py`|3|1|2|T-006|Fail-loud startup when tracing is on but unavailable.|
|`core/tests/test_user.py`|12|3|9|T-007|Staff user admin success paths (get, update, delete).|
|`todos/tests/test_pagination.py`|8|5|3|T-009|Pagination envelope, page, page size, max page size.|
|`todos/tests/test_todo.py`|9|6|3|T-008|Todo CRUD and ownership.|
|`billing/tests/test_billing.py`|24|10|14|T-010|Endpoint auth, checkout errors, CSRF-exempt webhook, bad signature.|
|`webhooks/tests/test_webhooks.py`|24|19|5|T-011|API ownership, dispatch fan-out, every SSRF test.|
|`notifications/tests/test_notifications.py`|18|8|10|T-012|API tests and the per-user "mark all read" scope.|
|`files/tests/test_files.py`|22|14|8|T-013|Ownership, key namespacing, upload validation (size, type, magic bytes, traversal).|
|`organizations/tests/test_organizations.py`|13|11|2|T-014|Membership, listing scope, invite permissions, leave rules.|
|`atlas/tests/test_atlas.py`|10|7|3|T-015|Generator structure and edge integrity; staff-only views.|
|`tests/smoke/test_check_dependencies.py`|9|9|0|-|Tooling: dependency gate the maintainer runs.|
|`tests/smoke/test_env_secrets.py`|7|7|0|-|Deploy safety: secret generation, guard check, doc sync.|
|`tests/smoke/test_gauntlet_results.py`|2|2|0|-|Tooling: gauntlet warning versus failure reporting.|
|`tests/smoke/test_release_script.py`|3|3|0|-|Tooling: release script never pushes or edits by accident.|
|`tests/smoke/test_settings_modules.py`|23|23|0|-|Deploy safety: production settings probes (TLS, HSTS, CSP, secrets).|
|`tests/smoke/test_smoke.py`|4|4|0|-|Smoke: token pair, todo variants, GET route sweep.|
|`tests/smoke/test_task_contract.py`|10|9|1|T-016|Backend-neutral task facade contract.|
|`tests/smoke/test_test_settings.py`|1|1|0|-|Regression: test tokens ignore local signing keys.|
|`tests/contract/test_openapi_contract.py`|5|5|0|-|OpenAPI contract (auth, envelope, camelCase, no versions).|
|`tests/contract/test_route_access.py`|17|17|0|-|Route classification, route regressions, cookie and CSRF contract.|
|`cli/tests/test_init.py`|1|1|0|-|Tooling: non-interactive init.|
|`cli/tests/test_setup.py`|6|6|0|-|Tooling: `.env` generation, secret strength, file mode, value preservation.|
|**Total**|**346**|**261**|**85**|16 tickets||

T-017 updates `core/README.md` after T-002 and T-007 merge, because the README
names tests that those tickets delete.

## Findings

- `notifications` and `organizations` are not in `INSTALLED_APPS`, and no flag
  installs them. Their test files cannot be collected, so they never run.
  T-012 and T-014 verify with `ruff`, `py_compile` and a test count.
- `webhooks` and `files` run only with `WEBHOOKS_ENABLED=true` and
  `FILES_ENABLED=true`. They are not in the pytest `testpaths`, and neither
  are `atlas/` and `cli/`. T-011 and T-013 set the flag in their Verify
  command.
- The two kept tests in `core/tests/test_ai_helpers.py` skip without Postgres
  and pgvector. `scripts/test_ai_db.py` runs them.

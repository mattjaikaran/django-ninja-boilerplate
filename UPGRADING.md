# Upgrading a platform

Use this guide when you merge a new boilerplate release into a platform that
derives from it. Each release section lists what changed, who it affects, and
what to do. Apply the sections in order, oldest first. `CHANGELOG.md` has the
full list. To copy single modules instead of merging, see
`docs/ADOPTING_UPDATES.md`.

## 1.14.0 to 1.15.0

### API changes for clients

None. The API keeps its paths, schemas and status codes. OpenAPI
`info.version` now reports the release (`1.15.0`) instead of `0.1`.

### Dependencies

| Package | Change | What to do |
|---|---|---|
| Django | Stays on 5.2 LTS (the lock is 5.2.19). | Nothing. Before you move to 6.0 or 6.1, run `just django-upgrade-check 6.1`. |
| Pillow | 12 to 13 | Re-test image uploads and avatar code. |
| filelock | 3 to 4 | Nothing, unless your own code imports it. |
| OpenTelemetry | 1.39 to 1.45 (instrumentation 0.60b1 to 0.66b2) | Check that your traces still reach your collector. |

### Production configuration

| Setting | Change | What to do |
|---|---|---|
| `ORGANIZATIONS_ENABLED`, `NOTIFICATIONS_ENABLED`, `BILLING_ENABLED` | New, default `false`. They install those apps and register their routes. In 1.14.0 the apps were commented out of `INSTALLED_APPS`. | If you uncommented an app by hand, set its flag to `true` instead. |
| `TODOS_ENABLED` | New, default `true`. `false` removes the todos app and its routes; the code stays as the reference app. | Set `false` in a product that does not ship todos. |
| `DEPLOY_NOTIFY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `HERMES_URL` | New, optional, read by `scripts/deploy.sh`. | Set them to get deploy messages; see `.env.deploy.example`. |
| `scripts/deploy.sh` | A failed VPS health check now exits 1 and sends `deploy_failed`. It used to warn and exit 0. | Check any automation that ran after a "successful" deploy with a failing health check. |
| Host ports for Centrifugo, Jaeger, MCP, Mailhog, Qdrant and Neo4j | Now read from env vars (`CENTRIFUGO_PORT`, `MCP_PORT` and others in `.env.example`), with the old values as defaults. | Nothing, unless you changed those ports in `docker-compose.yml` by hand: move the change to `.env`. |

### Your own code

| Change | What to do |
|---|---|
| `TodoController` takes `TodoService` through its constructor. | Pass a service to any subclass or test that built the controller with no arguments. |
| `api.settings.test` no longer installs `billing`. | Run billing tests with `BILLING_ENABLED=true`. |
| The ARCHITECTURE gate checks `repositories/` and `dtos/`, and the new APP-SHAPE gate checks app folders, file names and class names against `todos/`. | Run `just gauntlet-quick` and rename what it lists. |
| Generated apps use controller -> service -> repository by default. | Pass `--layers service` to keep the old shape (the service runs the queries, no repository). Existing apps are not changed. |
| `generate_feature chat --realtime` writes `services/chat_realtime_service.py` (was `realtime_service.py`), and `generate_feature organization` writes `controllers/organization_invitation_controller.py` (was `invitation_controller.py`), so they pass APP-SHAPE. | Rename the files in an app you generated before, and fix their imports. |
| Migrations must stay linear (MIGRATIONS gate). | Run `just migrations-check`; renumber with `just migrations-renumber --apply` instead of a merge migration. |
| `just gauntlet`, `gauntlet-quick` and `gauntlet-gate` print one line per gate and a failure tail; full logs go to `.gauntlet/last/`. | If a script or CI step parsed the old streaming output, pass `--verbose` or read `.gauntlet/last/report.json`. |
| `just pre-commit-install` installs hooks from the main checkout's venv. | Run `just pre-commit-install` once, so hooks work from every worktree. |

## 1.13.0 to 1.14.0

### API changes for clients

| Change | What to do |
|---|---|
| `GET /api/todos*/completed`, `/pending` and `/search`, and `GET /api/audit/actions`, `/models` and `/failed-logins`, returned `400` or `422` because an earlier `/{id}` handler caught them. They now return their lists. | Remove any client workaround for those errors. |
| Apps made with `generate_feature graphql` now serve /api/graphql/ instead of `/graphql/`; the bundled nginx proxies only /api/ and `/admin/`. Every query needs authentication and `users` is staff-only. | Point GraphQL clients at /api/graphql/. Regenerate an existing GraphQL app or port the changes by hand. |

### Production configuration

| Setting | Change | What to do |
|---|---|---|
| `CENTRIFUGO_API_KEY`, `CENTRIFUGO_TOKEN_SECRET` | `api.settings.prod` now refuses an empty value, as well as the published defaults. An empty token secret let anyone sign connection tokens. | Generate both with `python3 scripts/env_secrets.py fill`. |
| `JOURNEYS_ENABLED` | New. The `/admin/journeys/` pages are on by default and off in `api.settings.prod`, because the production image excludes `docs/`. | Nothing, unless you want the pages in another environment. |

### Your own code

Ninja binds a path pattern where it first appears, so any earlier handler on
`/{id}` (any method) shadows a later static path such as `/search`. The
CONVENTIONS gate (`ROUTE_ORDER`) and the smoke route sweep now catch it: the
sweep fails on any status of `400` or higher on a parameterless GET (`403` is
allowed for a regular user) and also runs as a staff user.

1. Run `just check-conventions` and `just test tests/smoke/test_smoke.py`.
2. For each route they list, move every `/{id}` handler of that controller
   after the static paths, or add `# route-ok: <reason>`.

| Change | What to do |
|---|---|
| `CamelCaseSchema.model_dump()` returns camelCase keys, so writing it to the ORM drops or crashes on multi-word fields. The new `model_dump_fields()` returns field names. The CONVENTIONS gate (`CAMEL_DUMP_TO_ORM`) now fails on `f(**x.model_dump())`, a stored dump unpacked the same way, and `setattr` loops over a dump. | Replace each flagged ORM write with `payload.model_dump_fields(...)`. Keep `model_dump()` for responses and logs. |
| `@log_api_call(include_payload=True)` now masks `code`, `otp`, `pin`, `refresh`, session and cookie fields, at any depth and in any case. | Nothing, unless a log consumer reads those values. |
| `api.settings.test` no longer reads `.env` unless `DJANGO_READ_DOT_ENV=1`, and selects Postgres only with `TEST_DB=postgres` (not `CI`). | Set test-only values in `api/settings/test.py` or the test command, not `.env`. Use `TEST_DB=postgres` where you used `CI=1`. |

### Code generators

`startapp_extended`, `generate_feature` and the `api_endpoint` generator now
emit a `JWTAuth` controller, an owner-scoped service and passing smoke and
permission tests. Apps you generated before keep their old code: compare them
with a fresh generation, and fix any controller that queries the ORM, wraps
lookups in `try/except`, or lacks `JWTAuth`. Several generators now stop when
the app folder exists.

A regenerated app has a different API from one generated before 1.14.0:

| Generator | Difference |
|---|---|
| `api_endpoint` | Same app as `startapp_extended`: fields `title` and `description`, owner `user` (was `name` and `created_by`). |
| `graphql` | Served at /api/graphql/; every field needs authentication; `users` is staff-only. |
| `chat` | Reactions use names (`heart`, `thumbs_up`); the message list uses `@paginate`, newest first. |
| `organization` | Decline an invitation with `POST /invitations/{id}/decline` (was `DELETE`); change the owner only through transfer-ownership. |
| `rbac` | Every route needs `IsAdminUser` except `GET /api/rbac/me/permissions`. |
| `team` | Writes need the team lead role; non-members get `404`. |

### Tooling and tests

| Change | What to do |
|---|---|
| No coverage floor and no mutation testing: `--cov-fail-under`, `--cov` in the default pytest options, the MUTATION gate, just mutation-test, `[tool.mutmut]` and `mutmut` are gone. | Remove local scripts that call them. `just test-coverage` still prints a report. |
| The pytest journey generator is gone: scripts/generate_e2e_tests.py, tests/user_journeys.example.yaml, tests/e2e/ and the `make` targets `generate-e2e`, `generate-e2e-dry`, `test-e2e`, `local-test-e2e`, `mutation-test`. | Move journeys to `docs/product/` and Playwright (see `docs/product/README.md`). |
| New gates: JOURNEYS (`just check-journeys`), TICKETS (`just tickets check`) and TEST-OPTIONAL (`just test-optional`). | Keep `docs/product/` and `docs/tickets/` valid, or remove the gates you do not use from `scripts/gauntlet.py`. |
| `pyyaml` is a base dependency; the `unit` pytest marker is gone. | Run `uv sync`. Remove `@pytest.mark.unit`. |
| The testing policy in `AGENTS.md` section 10 allows smoke, contract, permission and regression tests only. | Prune unit and mock tests with tickets, as `docs/tickets/PRUNE_PLAN.md` shows. |
| `generate_feature` lost `monitoring` and `cache` (they never worked), `subscription` (use `payments` or the `billing` app) and `file_storage` (use the `files` app), plus `--no-webhooks`. `redis` now defaults to the `cache_api` app name and generates a staff-only cache API. | Update scripts that call the removed choices. |
| `dnm add-app` runs `generate_feature api_endpoint` (or `startapp_extended` with `--no-wire`); `--docstrings` is gone. | Run it from inside the project. |
| `just doctor` now repairs by default (`uv sync`, hooks, `git worktree prune`, a missing `.env`, `just openapi`). | Use `just doctor --check` where you only want a report. |
| The full gauntlet adds GENERATORS; quick mode runs it when generator code changes. Flower's host port is `FLOWER_PORT`. | Nothing. |

### Verify

1. `just doctor` reports no FAIL.
2. `just gauntlet` passes.
3. With a production `.env`, `DJANGO_SETTINGS_MODULE=api.settings.prod python manage.py check` starts.

## 1.12.0 to 1.13.0

### Before you start

1. Read every section. Several changes refuse to start the app until you set
   new configuration.
2. Generate the secrets with `python3 scripts/env_secrets.py fill` (existing
   `.env`) and check them with `python3 scripts/env_secrets.py check`.
   `docs/ENV_SECRETS.md` lists each variable.
3. Update your frontend and other API clients for the API changes below
   before you deploy the backend.

### API changes for clients

| Change | What to do |
|---|---|
| `POST /api/auth/signup` returns `202` with `{"message": "Check your email to finish signing up.", "success": true}` for every address. It no longer returns `201` with the user, or `400` for a taken email or username. `400` now means only a password validation error. | Show a "check your email" screen. Do not read a user from the signup response. |
| Every response serialises by its camelCase alias (`userId`, `sessionId`, `stripePriceId`). Some dict responses used to send snake_case. | Read camelCase keys. Regenerate clients from `docs/openapi/openapi.json`. |
| Unsafe /api/ requests that carry no `Authorization` or `X-API-Key` header need `X-CSRFToken`, including /api/auth/login, /api/auth/refresh and /api/auth/logout. | Browser clients follow `docs/COOKIE_AUTH.md`. Bearer clients use `/api/token/*` or send `Authorization`. |
| A refresh token presented again more than 30 seconds after its rotation revokes every refresh token of the user and returns `401`. Inside 30 seconds the repeat only gets `401`. | On `401` from refresh, retry once (another tab may have rotated the cookie), then send the user to login. |
| A password change or reset revokes every refresh token of the user. | Expect `401` on the next refresh after a password change. |
| Password logins lock an (account, client IP) pair after 5 failures and a client IP after 20, for 15 minutes. Locked requests get `429`, even with the right password. | Show the `429` message. Do not retry automatically. |
| `POST /api/auth/logout` needs no access token. | Call it even when the access cookie has expired. |
| `DELETE /api/api-keys/{key_id}` and `POST /api/api-keys/{key_id}/rotate` take a UUID and return `404` for a missing key or another user's key (they returned `500`). A malformed id returns `422`. | Handle `404`. |
| This release supersedes the cookie-only auth change in commit `619422e`. The bearer routes /api/token/pair, /api/token/refresh and /api/token/verify stay and are throttled with the other credential endpoints. Login responses keep the tokens in the body as well as the cookies. | If you built on `619422e`, follow `docs/COOKIE_AUTH.md`: browsers use cookies and CSRF, other clients use `/api/token/*` or `Authorization: Bearer`. |

### Production configuration

#### TLS is required

`api/settings/prod.py` refuses to start with `USE_TLS=false`, because cookie
auth needs HTTPS outside localhost.

1. Put a TLS proxy in front of the bundled nginx (or of the single image) that
   sends `X-Forwarded-Proto: https`. The bundled nginx now passes that header
   through instead of overwriting it with `http`.
2. Set `USE_TLS=true`. The Compose prod services, `.env.deploy.example`, the
   production image and the single image default to `true`.
3. Expose nginx port 80 only to the TLS proxy.

Every process that loads `api.settings.prod` checks this, including Celery
workers and beat. `ALLOW_INSECURE_COOKIES=true` permits a local plain-HTTP
smoke run only; `ENVIRONMENT=production` rejects it.

HSTS stays at one year with `USE_TLS=true`. `includeSubDomains` and `preload`
are now opt-in: set `SECURE_HSTS_INCLUDE_SUBDOMAINS=true` and
`SECURE_HSTS_PRELOAD=true` only when every subdomain serves HTTPS.

#### Client IP: `NINJA_NUM_PROXIES`

Throttles, the login lockout and the audit log read the client IP from
`X-Forwarded-For`, trusting `NINJA_NUM_PROXIES` proxies. Set it to the number
of proxies that append to the header: `2` for a TLS proxy plus the bundled
nginx (Compose default), `1` for the single image behind one platform router
(image default). Too low merges every client into one IP, so one attacker
locks logins for the whole site. Too high lets clients choose their IP. See
the table in `docs/COOKIE_AUTH.md`.

Do not set `NINJA_NUM_PROXIES` in a development `.env` that you also use for
the prod profile: Compose interpolates it into the prod services.

#### Other settings

| Setting | Change | What to do |
|---|---|---|
| `API_DOCS` | Production defaults to `off`: /api/docs and /api/openapi.json return 404. | Set `staff` (admin login) or `public` if you need them. |
| `ADMIN_URL` | Admin mount path, default `admin/`. | To change it, also change `admin` in the nginx `location ~ ^/(api\|admin)/` regex. |
| `API_CSRF_EXEMPT_PATHS` | Default `["/api/token/", "/api/billing/webhooks/"]`. | Add the prefix of each signed webhook receiver you add. |
| `SENTRY_DSN` | With a DSN set and `sentry-sdk` missing, every `ENVIRONMENT` except `development` refuses to start. | Install the `sentry` extra (`UV_EXTRAS="sentry"`) or unset the DSN. |
| `CENTRIFUGO_TOKEN_SECRET`, `CENTRIFUGO_API_KEY` | Production refuses unset values and the published defaults. Compose requires `CENTRIFUGO_API_KEY` for every profile. | Generate both with `scripts/env_secrets.py`. |
| `SUPERUSER_PASSWORD` | Outside `ENVIRONMENT=development`, `create_superuser` and `docker-entrypoint.sh` refuse published defaults and passwords shorter than 12 characters. | Generate it with `scripts/env_secrets.py`. |
| `DJANGO_MCP_AUTH_TOKEN` | The dev `mcp` profile needs a token of 32 or more characters. | Development only. |
| `ORGANIZATIONS_ENABLED`, `NOTIFICATIONS_ENABLED`, `BILLING_ENABLED`, `FILES_ENABLED`, `WEBHOOKS_ENABLED` | Each optional app installs only when its flag is `true` (default `false`). Their tests skip while the flag is off. | Set the flags your platform uses, then run `migrate`. |

### Database and server

| Change | What to do |
|---|---|
| `psycopg2-binary` is replaced by `psycopg[binary,pool]` (psycopg 3). Web processes use Django's connection pool; `CONN_MAX_AGE` is `0` and must stay `0` with the pool. | Remove `psycopg2` imports and settings overrides that set `CONN_MAX_AGE`. Keep processes x `DB_POOL_MAX_SIZE` below Postgres `max_connections`. |
| Task workers fork after Django loads, which breaks an inherited pool. The Compose worker services set `DB_POOL_ENABLED=false`. | Set `DB_POOL_ENABLED=false` on every worker process you run outside Compose. |
| Production serves ASGI: Gunicorn with `uvicorn_worker.UvicornWorker` workers on `api.asgi:application` (`gunicorn.conf.py`). | Point custom Gunicorn commands, Procfiles and Helm values at `api.asgi:application`. |
| `billing` migration `0003` makes the Stripe ids unique only when set. | Run `migrate` if billing is installed. The old columns were already unique, so existing rows pass. |
| The new `core.ai` app (installed with `AI_ENABLED=true`) requires `Document.owner`. | New app: no data to migrate. Pass `user` to `hybrid_search` and `reachable`. |
| Refresh tokens that the old rotation issued have no `OutstandingToken` row. | Nothing to do: their next refresh records them. |

### Verify

1. `just gauntlet-quick` and `just openapi-check` pass.
2. `docker compose --profile prod config -q` passes with your deploy `.env`.
3. On the deployed site, log in, refresh, and log out in a browser, and check
   that every auth cookie has `Secure`.
4. Send 6 wrong passwords for a test account from one address, then log in
   from another address: the second login succeeds.

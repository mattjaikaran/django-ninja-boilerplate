# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Decisions app** (`decisions/`): configurable System One providers: open-source Laya (installed default), open-source CLM with an opt-in GPU Qwen3-8B Compose profile, hosted Jev, and a deterministic fake for tests. `POST /api/decisions/evaluate` accepts typed questions (`choice`, `score`, `noul`); `SYSTEMONE_PROVIDER` selects the provider. Providers never silently fall back. The endpoint requires JWT and is registered only when `ENABLE_DECISIONS` is true. Provider confidence is uncalibrated; the docs require a gate on consequential automation until you calibrate it on representative data.
- **pgvector fixtures** — `pgvector` is a base dependency and `DecisionFixture.embedding` is a native `vector` column. The initial migration creates the extension on PostgreSQL before the table; `docker/postgres/init/01-init.sql` creates it too. SQLite accepts the column type, so `just test` needs no setup.
- **Optional Jev extra** — `decisions-jev` installs the hosted TypeSafe SDK. Laya and its PyTorch dependencies ship in the base install so the open-source default runs after `uv sync`.
- **Single profiled Compose file**: `docker-compose.prod.yml` and `docker-compose.single.yml` are gone; `docker-compose.yml` carries the application, task backend, production, realtime, monitoring, mail, and MCP profiles. The default development stack starts Django, Postgres, Valkey, and one task backend. Mailhog and MCP are opt-in.
- **justfile** — replaces the Makefile, which is kept as `Makefile.legacy`. Recipes cover dev, test, database, MCP, search, quality, gauntlet, production, and deploy.
- **Agent Skills** (`.agents/skills/`, `SKILLS.md`) — harness-agnostic skills: `django-ninja-dev`, `decisions-app`, `docker-compose-profiles`, `rtk-ripgrep`, `system-design-atlas`.
- **`AGENTS.md`** — hand-maintained agent guidance with a "Patterns We Do Not Use" section.
- **Uniform task contract**: `api.tasks.shared_task` now provides `.delay()` and `.retry()` across Celery, Huey, django-q2, django-rq, and the new Dramatiq backend. Each backend has a tested Compose worker profile.
- **CLI-driven setup**: `just setup` runs the in-repo `dnm` CLI, asks for the task backend, updates `.env`, and then builds the selected stack.
- **CLM without an NVIDIA GPU**: `just clm-encoder-local` serves Qwen3-8B embeddings with llama.cpp and Metal on the host, and `CLM_ENCODER_URL` selects the new `decisions-clm-host` profile, which runs only `clm-api`. On an M2 Pro, a real three-question CLM decision through Django took 0.4 to 1.7 s. `clm-api` now builds from `python:3.12-slim` with CPU torch (about 900 MB, native on arm64 and amd64) instead of the 29 GB amd64 vLLM image: `contrastive-lm` declares vllm but never imports it. It reads its encoder from `CLM_EMB_URL`. A pipeline parity check (Qwen3-0.6B Q8_0 in llama.cpp against `transformers` bf16) gave cosine 0.998 to 0.9997 on 15 of 16 texts; the 8B quantization gap is unmeasured.
- **`eval_decisions`** (`just eval-decisions`): runs a labelled dataset through a provider and reports accuracy, mean confidence, expected calibration error, and coverage and accuracy at each threshold from 0.5 to 0.95. It ships 40 labelled support tickets. On that set, Laya scored 90 to 97.5% per question and was underconfident; CLM scored 72.5 to 92.5%.
- **Fixture similarity search**: `POST /api/decisions/similar` ranks stored `DecisionFixture` rows by cosine distance, using Qwen3-Embedding-0.6B from the new `embeddings` Compose profile (llama.cpp, CPU) or `just embedder-local`. `embed_decisions` (`just embed-decisions`) fills the vectors; re-seeding keeps vectors whose text is unchanged. The `embedding` column is now 1024 dimensions (migration `0002` clears old 1536-dimension vectors).

### Fixed
- `decisions/providers/jev.py`: use the current TypeSafe SDK `TypeSafeClient.system_one` API. Decode typed SDK answers, including `noul` probability and its uncertainty, before applying the escalation policy.
- `nginx/nginx.conf`: `gzip_proxied` had an invalid `must-revalidate` token, so nginx aborted with `[emerg] invalid value` and the production reverse proxy never started. The `centrifugo` upstream also pointed at the pre-rename service name; it now resolves per request, so nginx starts even when the `realtime-prod` profile is not enabled.
- `docker-compose.yml` and `nginx/Dockerfile`: the `prod` nginx service published `443:443` and mounted `./nginx/certs`, but `nginx/nginx.conf` listens on port 80 only and that directory does not exist. TLS terminates at an external proxy (`USE_TLS` in `.env.deploy.example`), so the unused port mapping, the certs mount, and `EXPOSE 443` are gone.
- `scripts/doctor.sh`: `((PASS++))` returns the old value, which is `0` on the first call, and a `0` exit status aborts the script under `set -e`. Every counter used post-increment, so `doctor` never completed. Its connectivity check also probed a `redis` service that does not exist (the compose service is `valkey`).
- `scripts/deploy.sh`: the VPS path still referenced the pre-rename service names (`django`, `db`, `redis`). Quick deploy silently skipped migrations behind `2>/dev/null || true`, and the full deploy aborted at step 4. The health probe now uses port 80 (nginx), since `django-prod` is `expose:`-only.
- Shell scripts (`db_setup`, `doctor`, `quickstart`, `setup`, and `run_migrations.sh`) called `docker-compose` with no profile, which starts nothing now that every service belongs to a profile. `setup.sh` and `quickstart.sh` also generated an `.env` pointing at a `redis` host instead of the `valkey` service.
- `Dockerfile`: removed the silent fallbacks (`2>/dev/null || uv pip install -e .`, `collectstatic … || true`) that could produce a base-only image or skip static collection without reporting it.
- `decisions`: wired the optional MCP registration into `DecisionsConfig.ready()` (it was never called), and removed the unused fixture schemas.
- `.env.example`: dropped `COMPOSE_PROFILES`. Some Compose versions merge it with `--profile`, which would start the dev services during a production deploy.
- `docker-compose.yml`: task workers no longer share the `dev` profile. `TASK_BACKEND` selects exactly one worker profile, while Mailhog and MCP remain opt-in.
- `scripts/setup.sh` and `scripts/quickstart.sh`: readiness checks targeted the `redis` service, which exists only in the `single` profile, so `setup.sh` waited 30 seconds and then aborted on a healthy dev stack. Both now probe `valkey`.
- `deploy/docker/Dockerfile.single`: the image could not build. It put uv on the wrong `PATH` (`/root/.cargo/bin` instead of `/root/.local/bin`), resolved dependencies fresh instead of from `uv.lock`, targeted Python 3.14 (no `pydantic-core` wheels), and set neither `ENVIRONMENT=production` nor a migration step. It now mirrors the production stage: Python 3.13, `uv sync --locked`, `ENVIRONMENT=production`, and `migrate` before Gunicorn.
- `deploy/centrifugo/config.json`: the engine address named `redis`, a host that only exists in the `single` profile, so both Centrifugo services failed to start with `error creating engine: malformed connection address`. The address now uses a host that resolves in each profile (`CENTRIFUGO_REDIS_ADDRESS`), and `health: true` enables `/health`, so the container healthcheck passes instead of reporting `unhealthy` forever.
- Pre-commit: `shellcheck` and `hadolint` failed on the committed tree, so no commit could pass the hooks. Fixed the shellcheck findings across the shell scripts, fixed the Dockerfile warnings, and set hadolint to `--failure-threshold warning` so info-level hints stay non-blocking.
- `justfile`: `just setup` aborted on a fresh clone because nothing created `.env`; it now delegates environment creation and backend selection to the `dnm` CLI. `just legacy` is variadic, so it accepts documented target arguments.
- `docker-compose.yml`: no service read `.env`. Compose passes only what each service pins, so most of the documented settings (including `SUPERUSER_*`) never reached the containers. Application services now read `.env` through `env_file` (`required: false`), while the internal addresses stay pinned so a developer's `.env` cannot redirect them.
- `docker-compose.yml`: the `single` `app` service pinned `REDIS_URL` but not `VALKEY_URL`, which settings read first, and `.env` names a `valkey` service the single stack does not run. It also let `.env` override the image's `DJANGO_SETTINGS_MODULE` and `ENVIRONMENT`, so the PaaS image ran development settings. Both are pinned now.
- `docker-compose.yml`: `django-prod` and the production Celery services never pinned `CELERY_BROKER_URL`, so they fell back to the `valkey://` default. kombu has no valkey transport, so production workers could not connect. They now use the `redis://` scheme against `valkey-prod`.
- `deploy/centrifugo/config.json`: Centrifugo does not expand `${...}` in its config file, so `token_hmac_secret_key` stayed the literal placeholder while Django signed JWTs with the real secret. Every realtime connection token would have been rejected. Compose now sets `CENTRIFUGO_TOKEN_HMAC_SECRET_KEY` (the name Centrifugo maps onto that key), and the config holds development defaults only.
- `.env.example`: `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` used the `valkey://` scheme, which kombu cannot use outside Docker. They now use `redis://` against the Valkey service.
- `create_superuser`: running twice reported a failure. It now reports that the superuser exists and exits successfully.
- `justfile`: `just setup` is now a complete CLI-driven bootstrap. It creates `.env`, asks for the task backend, generates Django and Centrifugo secrets, runs `doctor`, builds and starts the stack, migrates, and creates the superuser. `just seed` loads sample data.
- `deploy/docker/Dockerfile.single`: the image used a `sh -c` command that migrated before the database was reachable. It now uses `docker-entrypoint.sh`, which waits for the database, migrates, creates the superuser when `SUPERUSER_*` is set, and collects static files. The runtime stage installs `netcat-openbsd` for that wait, and the main Dockerfile no longer copies an entrypoint no service referenced.
- CI: the test matrix ran Python 3.14, where `pydantic-core` has no wheels and the install builds from source and fails. The matrix is 3.13 with the reason recorded, and the test job now installs from `uv.lock` instead of resolving fresh.
- `scripts/release.py`: the release commit stages only the version files, so it now refuses to run on a dirty tree instead of silently leaving work out of the tagged commit.
- `api/settings/common.py`: `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` defaulted to `VALKEY_URL`, whose `valkey://` scheme kombu cannot use. Any path that did not set them explicitly (a bare settings import, a deployment that skipped the template) produced a broker that could not connect. The default now derives the `redis://` form.
- `docker-entrypoint.sh` created a superuser whenever `SUPERUSER_*` was set, so a deployment that reuses `.env.example` would provision an admin account with the published template password. It now requires `CREATE_SUPERUSER=true`.
- `scripts/generate_secret_key.sh` rotated `SECRET_KEY` on every run, which invalidated sessions and JWTs and overwrote a key taken from a secret store. It now writes only when the value is missing or is still the template placeholder. It also writes the value with Python instead of `sed` (a key containing `&` spliced the old line into the new value) and single-quotes it, because Compose interpolates `$` in `.env` values.
- `just setup` starts the stack with `--wait`. Task workers now depend on healthy Django, so migrations finish before any worker consumes jobs.
- Production services pin `USE_STRUCTURED_LOGGING=true`: `.env` carries the development value, which otherwise disabled JSON logging in production. `centrifugo-prod` requires `CENTRIFUGO_TOKEN_SECRET` instead of starting with an empty signing key, and `.env.deploy.example` documents the realtime variables.
- `.env.example` contradicted itself about host versus container values, and neither template mentioned the superuser opt-in.
- `docker-compose.yml`: the `mcp` service never stayed up. `uv run` tried to create `.venv` inside the read-only bind mount and exited, and the container inherited the image healthcheck for port 8000 while it serves 8001, so it reported unhealthy even when running. It now uses the image virtualenv and probes its own port. Both faults were invisible until `just setup` started using `--wait`.
- `core/tasks.py` collided with the existing `core/tasks/` package, so Django and Celery could not import four core jobs. The jobs now live in `core/tasks/jobs.py` with stable task names and package exports.
- Task definitions imported Celery directly, Huey exposed no `.delay()`, and missing optional packages silently fell back to Celery. All task definitions now use the backend-neutral facade and invalid configurations raise `ImproperlyConfigured`.
- Development workers could start before migrations, inherited the Django HTTP healthcheck, and caused `docker compose --wait` to fail. Workers now wait for healthy Django and disable the unrelated image healthcheck.
- `just setup` now generates a unique Centrifugo signing secret. Production settings reject the published development values.
- `dnm init --yes` no longer opens the project-type prompt. Non-interactive scaffolding now uses the standalone layout by default.
- `pyproject.toml`: the Hatch wheel omitted the installed `atlas` app, so `django.setup()` failed with `ModuleNotFoundError: No module named 'atlas'` from an installed wheel. A test now checks that every local installed app is packaged.
- `docker-compose.yml`: the production services required `NINJA_JWT_SIGNING_KEY` through a Compose `:?` guard. Compose interpolates every service, so an `.env` without the key also broke `just dev`. `api/settings/prod.py` still refuses to start without a distinct key.
- `docker-compose.yml`: `CLM_API_KEY` reached only `clm-api`. Compose now passes it and the CLM address to `django`, `mcp`, every dev and production task worker, `django-prod`, and `app`, so a task that decides with CLM reaches the service.
- `just dev` and the other dev start recipes now run `up -d --build`. An existing checkout kept a Django image built before Laya joined the base install, so after a pull the default provider returned `The 'laya' package is missing`. A cached rebuild took 5 to 8 seconds here. `just up-build` is gone because `just dev` does the same. `just build` now also builds the selected task worker and, when `SYSTEMONE_PROVIDER=clm`, the `clm-api` image.
- `docker-compose.yml`: the dev `django` container had a 1G memory limit, and the first Laya decision was OOM-killed (exit 247). The limit is now `DJANGO_DEV_MEMORY_LIMIT`, default `4G`; the measured peak was about 3.1 GiB.
- `scripts/quickstart.sh`: the Docker path started only the `dev` profile, hid `up` errors, and pointed at a `just up-celery` recipe that does not exist. It now runs `just dev`, which starts the worker named by `TASK_BACKEND`, and prints the log on failure.
- `scripts/release.py` ignored every `--` argument except `--dry-run`, so `--help` or a mistyped flag ran a real release that committed, tagged, and pushed. It now uses `argparse`: unknown flags exit with an error before any change, `--help` prints usage, and push is opt-in through `--push`. `just release` and `just release-dry-run` pass their arguments through.
- `docker-compose.yml`: `django-prod` never served traffic. Its folded `command:` kept each deeper-indented gunicorn flag on its own line, so `sh -c` ran `--bind`, `--workers`, and the rest as commands (`sh: 4: --bind: not found`). It also crashed at settings import because `EMAIL_PORT=${EMAIL_PORT}` pinned an empty string (`invalid literal for int()`); the email pins are gone and settings defaults apply.
- `docker-compose.yml`: `centrifugo-prod` exited with `NOAUTH` because its Redis address omitted `REDIS_PASSWORD`. It also rejected every production browser WebSocket with 403 because only the dev origins were allowed; `CENTRIFUGO_ALLOWED_ORIGINS` now sets them.
- `docker-compose.yml`: `celery-worker-prod`, `celery-beat-prod`, and `flower` inherited the image healthcheck for Django on port 8000 and stayed unhealthy, so `up --wait` failed. The worker now answers `celery inspect ping`, Flower probes port 5555, and beat disables the check.
- `docker-compose.yml`: the `clm-encoder` and `clm-api` healthchecks called `python`, which the vLLM image does not ship (`exec: "python": executable file not found`). `clm-api` waits for a healthy encoder, so the CLM profile could never start on a GPU host. Both now call `python3`.
- `nginx/nginx.conf`: the static `upstream` pinned the `django-prod` container IP at startup, so recreating `django-prod` during a deploy left nginx returning 502. Both upstreams now resolve per request.
- `scripts/deploy.sh`: VPS quick deploy ran `git pull` and `up -d` without a build, so it restarted the old image and shipped no code. It now builds, migrates with the new image through `run --rm`, and only then replaces the containers, the same order as the full deploy; only the rollback marker and health check are skipped. The `--quick` help and the VPS dry-run output now describe those steps, and the dry run prints the real profile flags.
- `docker-compose.yml`: `celery-worker-prod` consumed only `-Q default,celery`, while `api/celery.py` routes `*cleanup*` tasks to `bulk` and email tasks to `emails`. The scheduled OTP and inactive-user cleanups never ran in production. The worker now consumes every configured queue, and the Helm chart default lists `default,emails,bulk`.
- `justfile`: `backend-profile` also accepted `TASK_BACKEND=django-q` and `django-rq`, which started the worker profile and then failed in `api/tasks/loader.py`. It now accepts only the loader's `django_q` and `django_rq`.
- `api/centrifugo.py`: `CentrifugoClient` logged an `error` payload from Centrifugo and returned it as a success, so a rejected publish looked delivered. It now raises `ExternalServiceError`.
- `single` / PaaS image: nothing served `/static/`, so the admin and API docs assets returned 404. `whitenoise` now serves collected static files; the `prod` nginx still serves them first.
- `mcp` service: django-ai-boost bound to `127.0.0.1` inside the container, so the published port 8001 was unreachable. It now binds `0.0.0.0` inside the container, and Compose publishes it on host loopback only.
- `decisions/mcp.py`: `register()` only logged a message, so the MCP server never exposed `evaluate_decision`. It now adds the tool to django-ai-boost's tool list during `django.setup()`; a live MCP client listed and called it.
- `api/settings/dev.py` hardcoded `ENABLE_DECISIONS` and `ENABLE_DECISION_MCP` to true, so the `.env` toggles did nothing and every dev worker (which has no dev extra) logged a missing-package warning. Both now follow `.env` (defaults: decisions on, MCP off), and the `mcp` service sets the MCP flag.
- `api/settings/dev.py` forced the console email backend, so `just up-mail` never received mail. The backend now follows `EMAIL_BACKEND`; `.env.example` shows the Mailhog values, and `up-mail` and `up-mcp` start the configured worker too.
- OpenTelemetry was never initialized: `init_tracing()` had no caller and the images lacked the packages, so Jaeger received nothing. `OTEL_ENABLED=true` now starts tracing in `CoreConfig.ready()` (and fails loud if the packages are missing), the images install the `observability` extra, and dev workers export to `jaeger:4317`.
- `decisions/providers/clm.py`: an unreachable CLM service or a rejected `CLM_API_KEY` surfaced as a generic 500. Both now return `provider_unavailable` with the address or setting to fix.
- `api/settings/dev.py`: runserver's autoreloader logged every watched file at DEBUG, including each torch module; it now logs at INFO.
- `docker-compose.yml`: dev `db` and prod `db-prod` shared the `postgres_data` volume, so a local prod run opened the dev database and failed with `password authentication failed`, or migrated it. Dev now uses `postgres_dev_data` and `valkey_dev_data`; `db-prod` and `db-single` keep `postgres_data`, so servers keep their data. **Upgrade step for local dev:** the dev stack starts with an empty database. To keep it, copy the old volume first: `docker run --rm -v <project>_postgres_data:/from -v <project>_postgres_dev_data:/to alpine cp -a /from/. /to/`. `scripts/db_setup.sh` now removes only the dev volume.

### Security
- `/api/realtime/connection-token` and `/api/realtime/subscription-token` had no authentication. Anonymous callers got subscription tokens for any channel (`sub` claim `None`). The controller now requires JWT, a user may subscribe only to their own `notifications:<user id>` channel, and a test fails when any new operation is public without being on an explicit allowlist.
- `POST /api/decisions/evaluate` and the MCP `evaluate_decision` tool no longer accept a `provider` override. Any JWT user could select `fake` or bypass the configured provider to reach Jev. The request schema now rejects unknown fields with 422.
- Upgraded dependencies to clear `pip-audit` advisories: Django 5.2.6 to 5.2.17, cryptography 46.0.1 to 50.0.1, pillow 11.3.0 to 12.3.0, urllib3 2.5.0 to 2.8.0, tornado 6.5.4 to 6.5.10, plus idna, anyio, click, orjson, pyasn1, ecdsa, and tablib. The only remaining advisory is `mcp`, pinned by `django-ai-boost`'s `fastmcp<4` requirement and used in the dev extra only.
- CI (`ci.yml`) and both Compose stacks now use `pgvector/pgvector:pg17`; the decisions migration creates the `vector` extension, which the plain `postgres:17-alpine` image cannot.

### Changed
- The task backend set now includes Dramatiq through the `dramatiq` optional extra and Compose profile.
- `docker-compose.yml`: the `db` image is now `pgvector/pgvector:pg17`.
- `scripts/release.py`, `scripts/deploy.sh`, the `cli` monorepo generator, and `.env.deploy.example` follow the new Compose layout and `just` recipes.
- Docs (`README.md`, `.context/PROJECT.md`, `.context/PROMPTS.md`, `scripts/quickstart.sh`): stale `Makefile` references now name `justfile`; the old runner stays at `Makefile.legacy`.
- Docs now match the code where they disagreed: the README quick start, command list, and profile table; the deleted `docker-compose.yml (prod profile)` references in `docs/MIGRATION.md` and `docs/REALTIME.md`; the removed `django-csp` settings in `SECURITY_CHECKLIST.md`; the raw `ninja.Schema` examples in `.context/CONVENTIONS.md`, `.context/ANTI_PATTERNS.md`, `.context/PROJECT.md`, and `.context/SYSTEM_PROMPT.md` (the repo's own gate rejects raw `Schema`); the `uv sync --dev` instruction in `setup.md` and `README.md` (`dev` is an extra: `--extra dev`); and `ROADMAP.md`, whose banner still read v1.8.0.
- `.env.example` documents the compose-only host ports and tuning knobs it omitted: `POSTGRES_PORT`, `VALKEY_PORT`, `PORT`, `GUNICORN_WORKERS`, `CELERY_CONCURRENCY`, `OTEL_SERVICE_NAME`, `USE_STRUCTURED_LOGGING`, and the `TEST_*` integration ports.
- `docs/REALTIME.md` claimed Centrifugo expands environment variables in its config file. It does not; the guide now names the environment variables Centrifugo actually reads.
- `ROADMAP.md` gains a status column: 1.9.0 to 1.11.0 were proposal labels and the items under them remain unshipped, and the Django 6.0 item is marked done.
- The dev stack publishes Postgres on 5433 and Valkey on 6380 instead of 5432 and 6379 (`POSTGRES_PORT`, `VALKEY_PORT`). `doctor` warns that 5432 conflicts with a local Postgres, and the application only ever reaches these services over the compose network, so the host ports are free to be offset. `just test-integration` moves to 5434/6381 to stay clear of the dev stack. `doctor` now reads the configured ports instead of assuming the defaults.
- `docs/TASK_BACKENDS.md` and `.env.example` used the `valkey://` scheme for the Celery broker and result backend, which kombu cannot use.
- `scripts/check_conventions.py`: the `ROUTER_USAGE` rule no longer flags dotted third-party attributes such as `laya.Router()`.

## [1.11.0] - 2026-08-15

### Added
- **Codebase Atlas** (`atlas/` app) — interactive isometric architecture map in the Unfold admin at `/admin/atlas/`. Blocks sized by real LOC per app, animated data-flow dots on edges, clickable data packets (request/response samples from the live OpenAPI schema plus masked audit-log bodies), drill-down into app components, and a playable request-flow trace. Generator: `python manage.py atlas` (or `make atlas`). Opt-in config via `ATLAS_ENABLED`, `ATLAS_DATA_PATH`, `ATLAS_CACHE_TTL`, `ATLAS_REAL_SAMPLES`; per-app prose via `atlas.py` modules (see `core/atlas.py`, `todos/atlas.py`) or `ATLAS_METADATA`. Staff-only, CSP-safe (static JS/CSS + same-origin JSON endpoint).
- **deepsec security scanning** (`docs/DEEPSEC.md`) — Makefile targets `deepsec-init`, `deepsec-scan`, `deepsec-review`, `deepsec-report`, `deepsec-revalidate` for the agent-powered [deepsec](https://github.com/vercel-labs/deepsec) vulnerability scanner, plus a CI workflow example.
- **Observability admin pages** — Health Check and Metrics now render as Unfold-styled staff pages at `/admin/observability/health/` and `/admin/observability/metrics/` instead of raw JSON/plain-text endpoints. The `/api/health/detailed` and `/api/metrics` endpoints stay unchanged for dashboards and Prometheus scrapers. The sidebar and dashboard quick links point at the new pages; the Flower (Celery) link appears only when `FLOWER_URL` is configured.
- **Celery worker health check** — the health page and `/api/health/detailed` now include a `celery` check (registered only when `TASK_BACKEND=celery`) that reports worker availability.
- **Release automation** (`scripts/release.py`, `make release`) — bumps the version across `pyproject.toml`, `api/settings/common.py`, the Makefile banner, and `VERSION`; retitles the CHANGELOG `[Unreleased]` section and inserts the compare link; syncs `uv.lock`; then commits, tags `vX.Y.Z`, and pushes. Default bumps the patch version; `make release VERSION=1.11.0` sets it explicitly; `--dry-run` previews the changes.

### Fixed
- `api/settings/common.py`: vcache cache backend path corrected to `django_vcache.backend.ValkeyCache` (the default `vcache` config crashed on any cache access with django-vcache 2.3.0).
- `docker-compose.yml`: `FLOWER_BASIC_AUTH` no longer uses required-var syntax, so `make up` works without the variable set; it defaults to `admin:password`.
- `Makefile`: deepsec targets renamed to `deepsec-*` to stop overriding the existing bandit `security-scan` target.
- `Makefile`: `make up` starts the core stack (db, valkey, django); `make up-full` starts everything. `build`, `down`, and `logs` cover all compose profiles.
- `docker-compose.yml`: container-to-container addresses (`DB_HOST`, `VALKEY_URL`, `REDIS_URL`, `CENTRIFUGO_URL`, OTEL endpoint, flower broker) are now fixed to compose service names. They were interpolated from `.env`, so a local-dev `DB_HOST=localhost` leaked into the containers and the django service could not reach Postgres.
- `docker-compose.yml`: Celery broker and result backend now use the `redis://` scheme (`redis://valkey:6379/0`). kombu has no `valkey://` transport, so flower and the celery workers failed with "No such transport: valkey". Host ports for postgres and valkey are configurable via `POSTGRES_PORT` / `VALKEY_PORT` to avoid clashes with local services.
- `core/admin/user_admin.py`: the user change form crashed with "'date_joined' cannot be specified ... non-editable field" because the custom `User` model marks `date_joined`/`updated_at` as `auto_now` and Django 5.2's base `UserAdmin` no longer declares `readonly_fields`. The admin now declares `readonly_fields` and explicit `fieldsets`/`add_fieldsets` that cover the custom profile, status, and preference fields.
- `templates/admin/observability/`: the Health and Metrics pages kept light status colors in dark mode because django-unfold's compiled CSS does not ship most `bg-*`/`dark:bg-*` shades. Status tints and kind badges now come from `core/static/observability/observability.css` with explicit `.dark` overrides.
- `atlas/static/atlas/atlas-scene.js`: the map fit now pads for the top edge labels and caps zoom at 1.3, so the top text stays visible on load instead of being clipped.

### Changed
- `core/audit/admin.py`: the AuditLog change form now autocompletes the user relation (`autocomplete_fields`) and the changelist shows a search help text.

## [1.10.0] - 2026-08-12

### Added
- **Deploy Notification** (`scripts/deploy.sh`) — `notify_deploy` POSTs a `deploy_complete` JSON envelope (`app`, `commit`, `env`, `frontend_url`, `backend_url`) to `DEPLOY_WEBHOOK_URL` after a successful provider deploy. Skips silently when the webhook is unset, respects `--dry-run`, and never blocks a deploy on an unreachable webhook.
- **Dependency Gate** (`scripts/check_dependencies.py`) — new gauntlet gate and pre-commit hook that fails when `pyproject.toml` changes without a matching `DEPENDENCIES.md` entry, so dependency additions get reviewed instead of silently merged.
- **Commit Message Style Hook** (`scripts/check_commit_msg.sh`) — commit-msg hook enforcing the tbaggery checks commitizen skips: subject ≤50 chars, no trailing period, body wrapped at 72 chars.

### Changed
- Pre-commit: registered the `dependencies` gate and `commit-msg-tbaggery` style checks as local hooks.
- `.env.deploy.example`: documented `DEPLOY_WEBHOOK_URL`, `DEPLOY_ENV`, `FRONTEND_URL`, `BACKEND_URL`.
- Version strings synced across `pyproject.toml`, `api/settings/common.py`, and `Makefile`.

## [1.9.0] - 2026-07-31

### Added
- **Convention Enforcement Gate** (`scripts/check_conventions.py`) — 12th gauntlet gate with 12 deterministic checks for AI anti-patterns: DRF imports, raw Schema usage, ModelSchema, ninja.Router, wrong decorator order, missing @handle_exceptions, unscoped queries, redeclared base model fields, missing __init__.py exports, pip usage, mocked ORM, unregistered controllers
- **Cross-Stack Convention Checker** (`scripts/check_cross_stack.py`) — 13th gauntlet gate for fullstack monorepos: naming consistency, schema parity, tooling consistency, rules consistency, gauntlet consistency
- **Four-Layer AI Defense System** spanning both backend and frontend:
  - Layer 1: System Prompt Injection (`.omp/APPEND_SYSTEM.md`) — non-negotiable guardrails injected into every AI session
  - Layer 2: Always-Apply Rules (`.omp/rules/`) — full convention references always in context
  - Layer 3: TTSR Mid-Generation Rules (`.omp/rules/ttsr-*.md`) — interrupts model mid-generation when it writes prohibited patterns
  - Layer 4: Deterministic Gauntlet Gates — post-generation pass/fail verification
- **Backend Convention Rules**: `backend-conventions.md`, `django-ninja-anti-patterns.md` (12 wrong/right examples)
- **Backend TTSR Rules**: `ttsr-framework-identity.md` (DRF/Schema/Router/ModelSchema interrupt), `ttsr-convention-violations.md` (decorator order/redeclared fields interrupt)
- **Frontend Convention Enforcement** in react-vite-boilerplate: `CLAUDE.md`, `.omp/APPEND_SYSTEM.md`, `.omp/rules/react-conventions.md`, `.omp/rules/react-anti-patterns.md`, `.omp/rules/ttsr-react-anti-patterns.md`, `scripts/check_conventions.ts` (8 TypeScript convention checks), `package.json` gauntlet scripts
- **Portable Gauntlet Export** (`make export-rules`) — bundles all 16 convention enforcement artifacts for use in any codebase
- **Adoption Prompt** (`docs/ADOPTION_PROMPT.md`) — copy-paste prompt to install the gauntlet in any codebase via AI
- **Mattstack Integration Docs** (`docs/MATTSTACK_INTEGRATION.md`) — division of labor between gauntlet gates and mattstack audit
- **Admin Dashboard Stats** (`core/admin/dashboard.py`) — system health metrics for django-unfold admin

### Fixed
- **58 convention violations** across the codebase: 35 schemas using raw `ninja.Schema` instead of `CamelCaseSchema`, 7 controllers missing `@handle_exceptions()`, 7 models redeclaring base fields, 5 `__init__.py` files missing exports, DRF import in code generator, pip install in Makefile

### Changed
- CI: `actions/upload-artifact@v4` → `@v7`
- Gauntlet expanded from 10 to 12 gates (added CONVENTIONS at #5, CROSS-STACK at #6)
- Makefile: added `check-conventions`, `check-cross-stack`, `export-rules` targets
- Pre-commit: added convention enforcement hook
- Dependabot: labels require repo setup (create `ci`, `dependencies` labels in GitHub)

## [1.8.0] - 2026-07-24

### Added
- **Constraint Tools Philosophy** — formalized the approach inspired by [Uncle Bob Martin's SwarmForge](https://github.com/unclebob/swarm-forge): agents write the deterministic tools that check constraints. Small programs, binary pass/fail, no human judgment required. If code survives all constraint tools, you don't need to read it. Documented in `docs/CONSTRAINT_TOOLS.md` and `CLAUDE.md`.
- **The Gauntlet** — 10-gate quality pipeline implementing the constraint tools philosophy. Every code change must survive all gates before merge:
  1. FORMAT (ruff format --check)
  2. LINT (ruff check — 50+ rule categories)
  3. TYPECHECK (mypy)
  4. SECURITY (bandit)
  5. ARCHITECTURE (layer enforcement)
  6. FILELENGTH (max 400 lines)
  7. TEST (pytest --cov-fail-under=35)
  8. MUTATION (mutmut — test quality validation)
  9. AUDIT (pip-audit — dependency vulnerabilities)
  10. DEPLOY (manage.py check --deploy)
- **Architecture enforcement** (`scripts/check_architecture.py`) — validates Controllers → Services → Models layering, prevents cross-app controller coupling, detects reverse dependencies. Works in both standalone and mattstack-scaffolded layouts.
- **Gauntlet orchestrator** (`scripts/gauntlet.py`) — runs all gates with `--quick`, `--ci`, `--fail-fast`, `--gate`, `--report` modes. Generates JSON reports for CI artifact upload.
- **Mutation testing** via `mutmut` — validates that tests actually catch bugs, not just execute code paths.
- **Makefile targets**: `gauntlet`, `gauntlet-quick`, `gauntlet-ci`, `gauntlet-gate`, `check-arch`, `mutation-test`, `mutation-results`, `security-scan`, `check-file-length`
- **CI gauntlet job** — architecture check, file length check, and full gauntlet run as a GitHub Actions job with artifact upload
- **Pre-commit architecture hook** — validates layer constraints on every commit
- **Commitizen commit-msg hook** — enforces conventional commit format
- **Constraint tool template** — documented pattern for writing new gates: deterministic, <400 lines, binary pass/fail, agent-writable. See `docs/CONSTRAINT_TOOLS.md`.

### Changed
- **Coverage threshold** raised from 25% to 35% (ratchet toward 80%) — every PR must maintain or increase coverage
- **VS Code settings** migrated from deprecated ruff-lsp to native Ruff extension (`ruff.nativeServer: "on"`, removed `ruff.showNotifications`)
- **Security scanning** in CI is now mandatory (bandit runs as a blocking gate, not `|| true`)
- **CLAUDE.md** expanded with gauntlet documentation, Definition of Done checklist, architecture rules, and mattstack-cli integration notes
- **`check-all` Makefile target** now delegates to `gauntlet --quick` instead of individual commands

### Dependencies
- Added (dev): `mutmut>=3.2.0`, `bandit[toml]>=1.8.0`, `commitizen>=4.1.0`

## [1.7.0] - 2026-07-04

### Changed
- **CLAUDE.md rewritten** — slim, Karpathy-inspired behavioral guidelines with 5 principles (ask don't assume, match complexity, surgical changes, flag uncertainty, suggest better approaches)
- **Version strings synced** — `pyproject.toml`, `api/settings/common.py`, and `Makefile` all report `1.7.0` (were drifted at `1.2.0` in settings/Makefile)
- **Consolidated env files** — removed duplicate `env.example`, canonical file is `.env.example` with all env vars documented (Valkey, task backends, API keys, JWT, email, Centrifugo, Stripe, OAuth)
- **Pre-commit ruff version** — bumped `v0.13.2` → `v0.15.10` to match `pyproject.toml`
- **Ruff isort known-first-party** — added all Django apps (billing, files, webhooks, organizations, notifications)
- **Hatch wheel packages** — added all satellite apps to `[tool.hatch.build.targets.wheel]`
- **Makefile cleanup:**
  - Fixed `install`/`sync`/`install-dev` to use `uv sync` instead of `uv pip install/sync`
  - Deduplicated `health`, `celery-worker`, `db-restore` targets (renamed duplicates to `local-*` and `db-restore-mgmt`)
  - Removed stale `env.example` fallback from `setup-env`
  - Added `typecheck`, `check-all`, `up-observability` targets
  - Synced version display to `v1.7.0`
- **Production settings fixes:**
  - Removed invalid `MAX_CONNS`/`MIN_CONNS` DB options (pgbouncer-only), added `CONN_HEALTH_CHECKS`
  - Fixed CSP to use django-csp 4.x `CONTENT_SECURITY_POLICY` dict format (was using legacy `CSP_*` vars)
- **Dev settings cleanup** — removed dead commented-out code (SQLite fallback, debug toolbar INSTALLED_APPS, django-extensions), removed orphaned `RUNSERVER_PLUS_PRINT_SQL`
- **Docker Compose** — added `VALKEY_URL` to celery-worker and celery-beat services, fixed header comment (`redis` → `valkey`)
- **Module exports** — `core/schemas/__init__.py` now exports API key schemas, `core/security/__init__.py` exports `APIKeyAuth`

## [1.6.0] - 2026-07-04

### Added
- **Valkey as default cache/broker** — wire-compatible Redis fork (BSD license) using `valkey/valkey:8-alpine` Docker image. Configurable via `CACHE_BACKEND` env var with three options:
  - `vcache` (default) — django-vcache with Rust I/O driver for maximum performance
  - `valkey` — django-valkey, stable fork of django-redis
  - `redis` — original django-redis backend for backward compatibility
- **API Key authentication** — built-in machine-to-machine auth via `X-API-Key` header
  - `APIKey` model with prefix-based lookup and SHA-256 hashed secrets
  - Scoped permissions (e.g., `read:todos`, `write:todos`)
  - Key rotation, revocation, and expiry support
  - CRUD endpoints at `/api/api-keys/` (JWT-protected)
  - Django admin integration via Unfold
- **Global orjson renderer** — 2-10x faster JSON serialization for all API responses
  - `ORJSONRenderer` and `ORJSONParser` for Django Ninja
  - Native datetime, UUID, dataclass, and numpy handling
- **Pluggable task queue backends** — `TASK_BACKEND` env var with full parallel support:
  - Celery (default, unchanged)
  - Huey (`uv sync --extra huey`)
  - django-q2 (`uv sync --extra django-q`)
  - django-rq (`uv sync --extra django-rq`)
  - Abstraction layer: `from api.tasks import shared_task`
  - Docker Compose profiles for each backend
- **ty type checker** — Astral's Rust-based type checker alongside mypy (`make ty`)
- **New documentation:**
  - `docs/TASK_BACKENDS.md` — comparison and setup guide for all task queue options
  - `docs/API_KEYS.md` — API key auth guide with usage examples
  - `docs/MIGRATION.md` — step-by-step migration guide for existing codebases

### Changed
- Docker Compose services renamed: `redis` → `valkey` (volumes: `redis_data` → `valkey_data`)
- `VALKEY_URL` is the new canonical env var (`REDIS_URL` kept as fallback alias)
- Celery broker/result URLs default to `VALKEY_URL` instead of `REDIS_URL`
- Makefile: new `valkey-*` targets, `redis-*` kept as aliases
- Railway deployment config updated for Valkey template

### Dependencies
- Added: `django-valkey>=0.4.1`, `django-vcache>=0.1.0`
- Added (optional): `huey>=2.5.0`, `django-q2>=1.7.0`, `django-rq>=2.10.0`, `rq>=1.16.0`
- Added (dev): `ty>=0.0.1a1`

## [1.5.1] - 2026-04-14

### Added
- **Reusable HTTP client** (`api/utils/http_client.py`) — async/sync wrapper around httpx
  - Pydantic `response_model` for automatic response parsing via `TypeAdapter`
  - Configurable retries, timeouts, and expected status code validation
  - `HttpClientError` with status code and response body for structured error handling
  - Module-level `http_client` singleton for zero-config usage
- **Granian migration prompt template** — step-by-step guide in `.context/PROMPTS.md` for swapping Gunicorn to Granian (Rust-based WSGI/ASGI server), covering Dockerfile, docker-compose, k8s, PaaS, logging, and optional ASGI mode
- **Mermaid diagram upgrades** — converted all ASCII box diagrams in `docs/ARCHITECTURE.md` and `docs/REALTIME.md` to Mermaid for native GitHub rendering

### Changed
- **Bumped all dependencies to latest versions**
  - Django ecosystem: django-environ 0.13.0, cors-headers 4.7.0, debug-toolbar 5.2.0, flags 5.0.14, import-export 4.3.7, js-asset 3.1.0, storages 1.14.6, unfold 0.52.0, ninja-extra 0.31.3, ninja-jwt 5.4.3, celery 5.5.2, celery-beat 2.7.0
  - Infrastructure: redis 7.4.0, flower 2.0.1, httpcore 1.0.9, uvloop 0.22.1, gunicorn 25.3.0, python-dotenv 1.2.2, charset-normalizer 3.4.7
  - Dev/testing: ruff 0.15.10, pytest 9.0.3, pytest-django 4.12.0, pytest-cov 6.2.1, pytest-mock 3.14.0, factory-boy 3.3.3
  - CLI deps: typer 0.24.1, rich 15.0.0, jinja2 3.1.6, pyyaml 6.0.3, questionary 2.1.1
  - CI actions: codecov/codecov-action v5→v6, softprops/action-gh-release v2→v3

### Removed
- **`requests`** — completely unused; httpx covers all HTTP client needs
- **`uvicorn`** — project uses WSGI (Gunicorn), not ASGI
- **`click`** — transitive dependency via Celery, no direct usage
- **`rich`** (root) — only used in CLI package, which declares its own copy

## [1.5.0] - 2026-03-30

### Added
- **Pydantic camelCase aliases** — automatic snake_case ↔ camelCase conversion for API schemas
  - `AliasPath` support for nested field access
  - `populate_by_name=True` for dual snake_case/camelCase input acceptance
- **Comprehensive LLM prompt templates** — framework-aware code generation prompts in `.context/`

## [1.4.0] - 2026-03-20

### Added
- **K3s deployment support** — lightweight Kubernetes deployment using plain YAML manifests
  - `deploy/k3s/namespace.yaml` — dedicated namespace
  - `deploy/k3s/secrets.yaml` — centralized secrets management with fail-safe placeholders
  - `deploy/k3s/configmap.yaml` — application configuration
  - `deploy/k3s/postgres.yaml` — PostgreSQL with local-path PVC (k3s default storage)
  - `deploy/k3s/redis.yaml` — Redis with password authentication and persistence
  - `deploy/k3s/django.yaml` — Django deployment (2 replicas) with init container migrations
  - `deploy/k3s/celery.yaml` — Celery worker and beat deployments
  - `deploy/k3s/ingress.yaml` — Traefik ingress (k3s built-in) with rate limiting middleware
  - `deploy/k3s/README.md` — full deployment guide with k3s vs k8s comparison
- **Nginx security headers** — HSTS with preload, `Permissions-Policy`, `X-Permitted-Cross-Domain-Policies`

### Changed
- **Hardened rate limits** — login and token verification endpoints increased from 10 to 20 req/min for better UX while maintaining brute-force protection
- **Tightened Content-Security-Policy** — removed `unsafe-inline`, `http:`, `blob:`; restricted `default-src` to `'self'`
- **Updated `X-XSS-Protection`** — changed from `1; mode=block` to `0` per modern best practice (CSP replaces it)
- **Stricter `Referrer-Policy`** — changed from `no-referrer-when-downgrade` to `strict-origin-when-cross-origin`

### Security
- **Fixed shell injection in `docker-entrypoint.sh`** — replaced inline Python heredoc (which interpolated env vars directly into code) with the safe `create_superuser` management command
- **Removed hardcoded fallback secrets from `docker-compose.yml`** — `SECRET_KEY`, `CENTRIFUGO_API_KEY`, `CENTRIFUGO_TOKEN_SECRET`, and `FLOWER_BASIC_AUTH` now use `${VAR:?must be set}` syntax that fails fast if env vars are missing, instead of falling back to guessable defaults like `admin:admin`

## [1.3.0] - 2026-02-26

### Added
- **Four progressive Todo controller patterns** — declarative, basic, partial, and full service-layer
  - `todos/controllers/todo_controller_declarative.py` — explicit `try/except`, no decorator magic
  - `todos/controllers/todo_controller_basic.py` — minimal, `get_object_or_404`, no custom decorators
  - `todos/controllers/todo_controller_partial.py` — `@handle_exceptions` + `@log_api_call` on writes only
  - `todos/controllers/todo_controller.py` — full decorator stack + injected `TodoService`
- **TodoService** (`todos/services/todo_service.py`) — extracted all business logic from the controller into a dedicated, testable service layer
- **Resend email backend integration** — `django-anymail[resend]` as default mailer with console fallback
- **Smoke test suite** — lightweight tests verifying all 4 controller route prefixes are reachable
- **Google-style docstrings** across all controllers and services
- **CLI `--docstrings` flag** — generated projects include Google-style docstrings by default
- **CLI `--email-backend` flag** — select email backend (Resend, console, SMTP) during project generation
- **Centrifugo Real-Time Messaging** — standalone WebSocket server replacing Django Channels
  - `api/centrifugo.py` — JWT token generation and HTTP client for publishing
  - Token endpoints: `POST /api/realtime/connection-token` and `/subscription-token`
  - Centrifugo server config with chat, notifications, and organization namespaces
  - Docker Compose service under `realtime` profile (port 8800)
  - Nginx WebSocket proxy at `/centrifugo/`
  - `make up-realtime` command
  - Full documentation at `docs/REALTIME.md`
  - 15 unit tests for token generation and client methods
- **`todos/README.md`** — dedicated docs for the todos example app with pattern table and code examples
- **`docs/ARCHITECTURE.md` — Progressive Controller Patterns section** with ASCII diagram, pattern comparison, and decorator stack diagram

### Changed
- `TodoController` now delegates all operations to an injected `TodoService`; controller methods are one-liners
- Bandit security scan moved to pre-push hook (was blocking commits on every save)
- Replaced Django Channels consumer templates with Centrifugo service templates in code generators
- Removed `channels` and `channels-redis` dependencies from chat and notification generators
- Updated notification generator `_send_in_app` to publish via Centrifugo
- Updated `make up-full` and `make down-full` to include `--profile realtime`

## [1.2.0] - 2026-02-17

### Added
- **Test settings module** (`api/settings/test.py`) - SQLite locally, PostgreSQL in CI
- **Resend email integration** (`django-anymail[resend]`) - Default mailer with console fallback
- **CLI `add-app` command** - Scaffold new Django apps with model/controller/schema/test stubs
- Missing migration for `deleted_at` and `deleted_by` fields on Todo model
- `ordering = ["-created_at"]` on Todo model Meta

### Changed
- Updated minimum Python version from 3.12 to **3.13** (supports 3.13 and 3.14)
- Updated default Python version in CI from 3.14 to **3.13**
- Updated CI test matrix to Python 3.13 + 3.14 (dropped 3.12)
- Updated Dockerfile base image from `python:3.14-slim` to `python:3.13-slim`
- Updated ruff target version from `py312` to `py313`
- Updated CLI tool to v1.2.0 with enhanced version output
- Updated CLI `test` command to set `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated UV version in CI from 0.5.0 to 0.6.0
- Updated pytest to use `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated pre-commit default Python from 3.14 to 3.13
- Updated all `pip install` references to `uv add`
- Updated all documentation to reflect Python 3.13+ requirement

### Fixed
- Fixed test suite to run locally without PostgreSQL (SQLite fallback)
- Fixed `test_signup` test URL from `/api/users/signup` to `/api/auth/signup`
- Fixed Todo model missing `deleted_at`/`deleted_by` migration (schema mismatch)
- Fixed Todo model ordering (was unspecified, now `-created_at`)
- Fixed CLI `lint` command dead code in formatter branch
- All 26 tests now pass locally and in CI

## [1.1.0] - 2026-02-05

### Added
- **Audit Logging System** - Comprehensive compliance tracking (GDPR, SOC2, HIPAA ready)
  - Automatic model change tracking via Django signals
  - API request/response logging middleware
  - Authentication event tracking (login, logout, failures)
  - Immutable audit trail with preserved user emails
  - Admin interface for viewing and filtering logs
  - REST API endpoints for audit log queries

- **Feature Flags System** - Gradual rollouts and A/B testing
  - Boolean, percentage-based, and A/B test flag types
  - User and environment targeting
  - Time-based activation windows
  - Middleware for automatic flag attachment to requests
  - Admin panel management with bulk actions
  - REST API for flag management and evaluation

- **Observability Stack** - Production monitoring
  - OpenTelemetry distributed tracing with Jaeger integration
  - Prometheus metrics endpoint (`/api/metrics`)
  - Structured JSON logging with trace context
  - Enhanced health checks with component status
  - Request timing and slow request logging
  - Docker Compose profile for observability services

- **Task Management Improvements** - Enhanced Celery task handling
  - Progress tracking with `ProgressTask` base class
  - Dead Letter Queue (DLQ) for failed tasks
  - Periodic task scheduling API
  - Task status and progress REST endpoints
  - `TaskResult` model for persistent task tracking
  - Bulk retry and resolution for failed tasks

- **Testing Utilities** - Comprehensive testing toolkit
  - Contract tests with Schemathesis for OpenAPI validation
  - Load tests with Locust for performance testing
  - Enhanced test client with auth helpers
  - Custom assertions for API responses
  - Factory utilities for test data generation

- **OpenAPI Enhancements** - SDK generation and API tools
  - TypeScript SDK generator
  - Python SDK generator
  - Postman collection export
  - Insomnia collection export
  - API changelog generator for version comparison
  - OpenAPI spec validation

- **GraphQL Generator** - Optional Strawberry GraphQL setup
  - Management command to scaffold GraphQL for any app
  - JWT-authenticated GraphQL endpoint
  - Query and mutation types with examples
  - Custom context class with user access

### Changed
- Updated Python requirement to 3.13+ (from 3.11+)
- Updated all Dockerfiles to Python 3.13-slim
- Updated CI actions to latest versions (checkout@v6, setup-python@v6, setup-uv@v7)
- Consolidated `get_client_ip` utility to single canonical source
- Split pagination module into subpackage (`api/pagination/`)
- Split throttling module into subpackage (`api/throttling/`)
- Added `OffsetPaginator` and `TokenBucketRateLimiter` aliases for clarity

### Removed
- Legacy `todo_controller_legacy.py`
- Unused flake8 and isort configuration files (Ruff handles all linting)

## [1.0.0] - 2026-01-26

### Added
- **Developer Experience (DX) Overhaul**
  - One-command setup: `make setup` for complete project bootstrap
  - Environment doctor: `make doctor` validates Python, Docker, ports, and config
  - Docker Compose profiles for flexible service management:
    - `make up` - Core services (db, redis, django)
    - `make up-celery` - With Celery worker and beat
    - `make up-monitoring` - With Flower dashboard
    - `make up-full` - All services
  - `.env.development` with sensible defaults (committed)
  - `.dockerignore` for optimized Docker builds
  - VSCode configurations (settings, launch, tasks, extensions)
  - VERSION file for semantic versioning
  - CHANGELOG.md following Keep a Changelog format

- **CLI Tool (`django-ninja-matt`)**
  - Interactive project scaffolding with Typer + Rich
  - Commands: `dnm init`, `dnm doctor`, `dnm setup`
  - Standalone API and Monorepo project types
  - Feature selection (Celery, Redis, auth methods)
  - Deployment target configuration

- **Deployment Configurations**
  - Single-container Dockerfile for PaaS (`deploy/docker/Dockerfile.single`)
  - Railway configuration (`deploy/paas/railway.json`, `railway.toml`)
  - Render Blueprint (`deploy/paas/render.yaml`)
  - Kubernetes Helm chart with:
    - Backend deployment with health checks
    - Celery worker deployment
    - Celery beat deployment
    - Flower monitoring deployment
    - PostgreSQL and Redis subcharts
  - `docker-compose.single.yml` for single-container local testing

- **CI/CD**
  - GitHub Actions workflow for lint, test, Docker build
  - Security scanning with pip-audit
  - Automated releases workflow
  - Dependabot configuration for dependency updates

- **Infrastructure**
  - Celery worker and beat services in Docker Compose (profile-based)
  - Flower monitoring service (profile-based)

### Changed
- Enhanced `scripts/setup.sh` with `--auto` mode for CI/CD
- Improved Makefile with profile-based commands
- Updated docker-compose.yml with service profiles

## [0.8.0] - 2026-01-25

### Added
- OTP (One-Time Password) authentication support
- New user model fields including metadata
- Base model, service, and schema patterns
- SQL dump/restore commands
- Rate limiting middleware
- New make commands for data management

### Changed
- Updated user model with enhanced fields
- Improved authentication decorators

## [0.7.0] - 2026-01-20

### Added
- Django Ninja JWT authentication
- Custom user model with email-based auth
- Todo app as example CRUD implementation
- Comprehensive API documentation (Swagger/ReDoc)
- Health check endpoint
- Docker development environment with hot reload
- PostgreSQL 17 and Redis 7.2 services
- UV package management integration
- Ruff linting and formatting
- pytest test suite with coverage
- Pre-commit hooks configuration

### Changed
- Migrated from pip to UV for package management

## [0.6.0] - 2026-01-15

### Added
- Initial Django 5.2 + Django Ninja setup
- Basic project structure
- Docker Compose configuration
- Makefile for common operations

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.10.0 | 2026-08-12 | Deploy notification, dependency gate, commit-msg style checks |
| 1.9.0 | 2026-07-31 | Convention enforcement, cross-stack checker, four-layer AI defense |
| 1.8.0 | 2026-07-24 | The Gauntlet, constraint tools, mutation testing, architecture enforcement |
| 1.7.0 | 2026-07-04 | CLAUDE.md rewrite, version sync, env consolidation, Makefile cleanup |
| 1.6.0 | 2026-07-04 | Valkey, API keys, orjson, pluggable task queues, ty type checker |
| 1.5.1 | 2026-04-14 | Dep cleanup, HTTP client, Mermaid diagrams, granian prompt |
| 1.5.0 | 2026-03-30 | Pydantic camelCase aliases, LLM prompt templates |
| 1.4.0 | 2026-03-20 | K3s deployment, security hardening, nginx headers |
| 1.3.0 | 2026-02-26 | 4 controller patterns, TodoService, Resend, Centrifugo real-time |
| 1.2.0 | 2026-02-17 | Python 3.13+ default, test fixes, migration fixes |
| 1.1.0 | 2026-02-05 | Audit logging, feature flags, observability, task management |
| 1.0.0 | 2026-01-26 | DX Overhaul, CLI tool, K8s Helm chart |
| 0.8.0 | 2026-01-25 | OTP, enhanced user model, rate limiting |
| 0.7.0 | 2026-01-20 | JWT auth, UV, Docker dev environment |
| 0.6.0 | 2026-01-15 | Initial release |

[Unreleased]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.11.0...HEAD
[1.11.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.8.0...v1.0.0
[0.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/releases/tag/v0.6.0

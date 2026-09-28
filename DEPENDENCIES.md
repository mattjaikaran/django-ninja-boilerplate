# Dependencies

This file records dependency changes so they get reviewed instead of merging
silently. The `DEPENDENCIES` gauntlet gate fails when `pyproject.toml` changes
without a matching entry here.

## Tooling changes

- Removed the stale `api.pagination.offset` mypy override. Ninja Extra now
  provides pagination, and this module no longer exists. No package changed.
- Added `atlas` to the Hatch wheel package list. It is an installed app, so a
  built wheel without it failed `django.setup()`. No package changed.
- The Docker images (`Dockerfile`, `deploy/docker/Dockerfile.single`) now
  install the existing `observability` extra, so `OTEL_ENABLED=true` works
  without a rebuild. No new package; the extra was already locked.
- `decisions/mcp.py` appends `evaluate_decision` to
  `django_ai_boost.server_fastmcp.TOOLS`. django-ai-boost has no public
  extension hook, so an upgrade that renames that list breaks the tool;
  `decisions/tests/test_mcp.py` and a live `list_tools` call catch it.
- New Compose image, no Python package: `ghcr.io/ggml-org/llama.cpp:server-b11223`
  (`embedder` service, `embeddings` profile) serves Qwen3-Embedding-0.6B
  (`Qwen/Qwen3-Embedding-0.6B-GGUF`, Q8_0, about 640 MB). Pinned to a build
  tag; the rolling `server` tag changes daily.
- Host tool, no Python package: `just clm-encoder-local` and
  `just embedder-local` need `llama-server` from `brew install llama.cpp`.
  The CLM encoder uses `Qwen/Qwen3-8B-GGUF` Q8_0 (8.7 GB).
- `deploy/docker/Dockerfile.clm` now installs, outside the project lock:
  CPU `torch==2.14.0`, `numpy==2.5.3`, `requests==2.34.2`,
  `huggingface-hub==0.36.2`, `uvicorn==0.53.0`, `fastapi>=0.115,<1`, and
  `contrastive-lm==0.1.0` with `--no-deps` (it declares vllm but never
  imports it). Versions match `uv.lock` where the project also uses them.

## Policy

- Base dependencies install for everyone. Laya is the open-source default, so
  its PyTorch and Transformers dependencies are required even when decisions
  endpoints are disabled. Expect larger installs and production images.
- Situational packages go in an optional extra under
  `[project.optional-dependencies]` and fail loud when absent.

## Supported Django versions

`Django>=5.2,<7.0`. **5.2 LTS** (the default) and **6.0** are supported and
covered by CI; the whole suite passes on both, on SQLite and PostgreSQL.

### Django 6.1: measured, not supported

Historic experiment, 2026-09: in a throwaway environment that omitted
`django-celery-beat` and used a **temporary** build of `api/settings/common.py`
that registered that app conditionally, the **PostgreSQL** suite passed 147
tests on Django 6.1.1. That measurement does not describe this tree, and it was
never a supported configuration: the conditional registration was reverted, so
the shipped settings require the app in `INSTALLED_APPS` and a 6.1 environment
without it fails at import. With the package present the install cannot resolve
at all, because `django-celery-beat` 2.9.0 is the newest release and caps
`Django<6.1`, while `CELERY_BEAT_SCHEDULER` names its database scheduler.
Celery is the default task backend, so making the package optional would drop
periodic tasks from a default install, which is worse than supporting the older
Django.

**A supported 6.1 install is therefore not possible today, and 6.1 stays out of
the matrix.** Revisit when `django-celery-beat` ships a release allowing 6.1:
add `"6.1"` to the matrix in `.github/workflows/ci.yml` and run the suite on
both PostgreSQL and SQLite.

### Django 6.0

Previously impossible because `django-celery-beat` capped `Django<6.0`. Version
**2.9.0** raised that cap to `<6.1`, so `django-celery-beat>=2.9.0` is required
and Django 6.0 resolves.

Several dependencies declare support for 5.2 but not yet for 6.0. They are
**verified working on 6.0 by the test suite**, so nothing is excluded today:

| Package | Declared | Status on 6.0 |
|---|---|---|
| `django-import-export` 4.x | 5.2 | Tested passing (5.0.0 adds declared 6.0 support) |
| `django-storages`, `django-csp`, `django-ninja-jwt` | 5.2 | Tested passing |

## Supported Python versions

**3.13** in CI. **3.14 is excluded** because `pydantic-core` 2.33.2 publishes no
cp314 wheels, so the install builds it from source and fails on a runner with no
Rust toolchain. Add 3.14 back once pydantic-core ships cp314 wheels.

## Base dependencies

| Package | Version | Why |
|---|---|---|
| `pgvector` | `>=0.5.0` | Native `vector` column for `DecisionFixture.embedding`. Small, pure Python; the initial migration creates the Postgres extension. SQLite accepts the column type, so the test suite needs no special setup. |
| `laya` | `>=0.3.11` | Open-source default System One engine. Includes PyTorch and Transformers; the first prediction downloads a checkpoint from Hugging Face. A standard `uv sync` must support the default provider. |
| `torch` | `>=2.1` | Required by Laya. uv installs the official CPU wheel on Linux to keep Django images free of CUDA libraries; macOS retains its native PyPI wheel and MPS support. |
| `whitenoise` | `>=6.9` | Serves `/static/` from Gunicorn in the `single` and PaaS image, which has no nginx. Without it the admin and `/api/docs` assets returned 404 there. The `prod` profile's nginx still serves static files first. |

## Known constraints

- `django-vcache` publishes **manylinux wheels only**. On Linux (CI, Docker)
  3.x installs from a wheel; on macOS/Apple Silicon there is no wheel, and
  3.2.0 fails to compile (`no method named set_user_timeout`). A blanket
  `uv lock --upgrade` therefore breaks on macOS. `pyproject.toml` caps it at
  `<3.2.0` and the lockfile stays on the known-good 2.3.0; widen the cap after
  testing 3.x on macOS.
- Every local installed app, including `decisions` and `atlas`, is in the
  wheel package list, so installs from a built wheel can run `django.setup()`
  and load the configured provider. `core/tests/test_packaging.py` checks it.
- Keep `PYTHONOPTIMIZE=1` in production. Laya loads Transformers models;
  Transformers reads its own class docstrings while building model documentation.
  Optimization level 2 removes those docstrings and breaks model loading.
- `mcp` is held below 1.28 by `django-ai-boost`'s `fastmcp<4` requirement. It
  is a dev-only dependency and does not ship in the production image.

## Optional extras

### `dev`

| Package | Version | Why |
|---|---|---|
| `django-ai-boost` | `>=0.9.0` | Backs the dev-profile `mcp` compose service (`django-ai-boost --transport sse --port 8001`). Pulls `fastmcp`. |


### `decisions-jev`

| Package | Version | Why |
|---|---|---|
| `typesafe-sdk` | `>=0.6.0` | Hosted TypeSafe ("Jev") decision client. The provider uses `TypeSafeClient.system_one` and typed answer objects from this SDK version. |

### `dramatiq`

| Package | Version | Why |
|---|---|---|
| `dramatiq[redis]` | `>=1.17.0` | Fifth task backend. The Redis extra lets its worker use the existing Valkey service. The task facade fails loud when the extra is absent. |

The `decisions` app is registered in `INSTALLED_APPS` for every environment,
but its controller is registered only when `ENABLE_DECISIONS` is true. Laya is
installed by default; the Jev client remains optional. CLM uses the existing
`httpx` dependency, with its GPU model service deployed separately.

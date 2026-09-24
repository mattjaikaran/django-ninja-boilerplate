# Dependencies

This file records dependency changes so they get reviewed instead of merging
silently. The `DEPENDENCIES` gauntlet gate fails when `pyproject.toml` changes
without a matching entry here.

## Policy

- Base dependencies stay small and required. They install for everyone.
- Heavy or situational packages go in an optional extra under
  `[project.optional-dependencies]`.
- An optional extra must fail loud when absent, not degrade silently.

## Supported Django versions

`Django>=5.2,<7.0`. Both **5.2 LTS** (the default) and **6.0** are supported and
covered by CI; the whole suite passes on both (SQLite and PostgreSQL).

Django 6 was previously impossible because `django-celery-beat` capped
`Django<6.0`. Version **2.9.0** raised that cap to `<6.1`, so the project now
requires `django-celery-beat>=2.9.0` and Django 6 resolves.

Several dependencies declare support for 5.2 but not yet for 6.0. They are
**verified working on 6.0 by the test suite**, so nothing is excluded today:

| Package | Declared | Status on 6.0 |
|---|---|---|
| `django-import-export` 4.x | 5.2 | Tested passing (5.0.0 adds declared 6.0 support) |
| `django-storages`, `django-csp`, `django-ninja-jwt` | 5.2 | Tested passing |

If a package ever genuinely breaks on Django 6, move it into an optional extra
and guard its `INSTALLED_APPS` entry, then omit that extra on Django 6. PEP 508
markers cannot key on another distribution's version, so per-version extras are
the only mechanism for a true subset.

## Base dependencies

| Package | Version | Why |
|---|---|---|
| `pgvector` | `>=0.5.0` | Native `vector` column for `DecisionFixture.embedding`. Small, pure Python; the initial migration creates the Postgres extension. SQLite accepts the column type, so the test suite needs no special setup. |

## Known constraints

- `django-vcache` publishes **manylinux wheels only**. On Linux (CI, Docker)
  3.x installs from a wheel; on macOS/Apple Silicon there is no wheel, and
  3.2.0 fails to compile (`no method named set_user_timeout`). A blanket
  `uv lock --upgrade` therefore breaks on macOS. `pyproject.toml` caps it at
  `<3.2.0` and the lockfile stays on the known-good 2.3.0; widen the cap after
  testing 3.x on macOS.
- `mcp` is held below 1.28 by `django-ai-boost`'s `fastmcp<4` requirement. It
  is a dev-only dependency and does not ship in the production image.

## Optional extras

### `dev`

| Package | Version | Why |
|---|---|---|
| `django-ai-boost` | `>=0.9.0` | Backs the dev-profile `mcp` compose service (`django-ai-boost --transport sse --port 8001`). Pulls `fastmcp`. |

### `decisions-laya`

| Package | Version | Why |
|---|---|---|
| `laya` | `>=0.3.11` | Default in-process System 1 decision engine. **Opt-in**: pulls `torch` and `transformers`, so it is never installed by default. Without it, `LayaProvider` fails loud with the install command. |

### `decisions-jev`

| Package | Version | Why |
|---|---|---|
| `typesafe-sdk` | `>=0.1.0` | Client for the hosted TypeSafe ("Jev") decision API. |

The `decisions` app is registered in `INSTALLED_APPS` for every environment,
but its controller is registered only when `ENABLE_DECISIONS` is true. Neither
extra is required for the test suite, which runs against `FakeProvider`.

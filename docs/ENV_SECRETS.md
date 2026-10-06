# Generated environment secrets

`scripts/env_secrets.py` holds the one list of secrets that setup generates
into `.env`. `dnm init`, `dnm setup`, `just setup-env`, `just setup-services`,
`scripts/setup.sh`, and `scripts/quickstart.sh` all call it. mattstack calls
the same script in the cloned backend; use `list --json` to read the list.
The script uses the Python standard library only.

## Variables

| Variable | Generated value | Why it must be set |
|---|---|---|
| `SECRET_KEY` | 64 random letters and digits | `api/settings/prod.py` refuses an empty key; Compose `:?` guard. |
| `NINJA_JWT_SIGNING_KEY` | 64 characters, distinct from `SECRET_KEY` | `prod.py` refuses an unset key or one equal to `SECRET_KEY`. |
| `CENTRIFUGO_TOKEN_SECRET` | 64 characters | `prod.py` refuses the published defaults; Compose `:?` guard. |
| `CENTRIFUGO_API_KEY` | 64 characters | `prod.py` refuses the published defaults; Compose `:?` guard. |
| `CENTRIFUGO_ADMIN_SECRET` | 64 characters | Compose `:?` guard (dev admin UI). |
| `CENTRIFUGO_ADMIN_PASSWORD` | 32 characters | Compose `:?` guard (dev admin UI). |
| `DJANGO_MCP_AUTH_TOKEN` | 64 characters | `just up-mcp` refuses tokens shorter than 32 characters. |
| `DB_PASSWORD` | 32 characters | Compose `:?` guard; Postgres password. |
| `REDIS_PASSWORD` | 32 characters | `valkey-prod` runs with `--requirepass`. |
| `FLOWER_BASIC_AUTH` | `admin:` + 32 characters | Compose `:?` guard (`monitoring` profile). |
| `NEO4J_PASSWORD` | 32 characters | Compose `:?` guard (`graph` profile). |
| `SUPERUSER_PASSWORD` | 32 characters | `docker-entrypoint.sh` and `create_superuser` refuse published defaults and passwords shorter than 12 characters outside development. |

Values use letters and digits only, so no value needs quoting in `.env`, in a
`redis://:PASSWORD@host` URL, or in a shell argument, and Compose never
interpolates a `$`.

## Order of setup

Compose interpolates every service, whatever profile you start, so any
`docker compose` command fails while one of the guarded secrets is unset.
Run `just setup-env` (or `dnm setup`) first. On an existing `.env` it
generates only the missing secrets.

## Commands

All commands take `--root DIR` (default: the current directory) and
`--env-file PATH` (default: `ROOT/.env`). No command prints a secret value;
they print variable names and counts only.

| Command | Result | Exit status |
|---|---|---|
| `create [--template PATH \| --no-template] [--only A,B \| --exclude A,B] [--set KEY=VALUE ...]` | Writes a new env file with mode `0600` from the template (default `ROOT/.env.example`, or the secrets only with `--no-template`). `--set` adds non-secret values. | 0; 1 when the file exists (it is never replaced); 2 for an unknown secret name. |
| `fill` | Generates missing, empty, or placeholder secrets in an existing file. | 0; 1 when the file is missing. |
| `check` | Names unset, placeholder, or too-short secrets. | 0; 1 when one is weak. |
| `list [--json]` | Prints the names, or the JSON below. | 0 |

`list --json` prints this shape (version 1; new fields can be added, existing
fields keep their meaning):

```json
{
  "version": 1,
  "secrets": [
    {"name": "SECRET_KEY", "kind": "key", "length": 64, "min_length": 50, "stored": false, "prefix": ""},
    {"name": "FLOWER_BASIC_AUTH", "kind": "basic_auth", "length": 32, "min_length": 12, "stored": false, "prefix": "admin:"}
  ]
}
```

- `kind`: `key`, `password`, or `basic_auth` (value is `prefix` plus the
  random part).
- `length`: length of the generated random part.
- `stored`: `true` when a data volume keeps the value from its first start.

To merge secrets into a file that holds other settings, write those settings
to a template with empty secret values, then run
`create --env-file .env --template that-template`. Run `create` once per
environment file; each call generates new values.

## Rules

- `create` and `fill` add the env file name to the `.gitignore` next to it
  when no pattern ignores it. Never commit `.env`.
- `fill` keeps every value you set, even a short one; `check` reports those.
  For `DB_PASSWORD` and `NEO4J_PASSWORD` it keeps placeholders too, because
  the data volume stores the first value. A missing one is generated, with a
  warning: if that volume already exists, set the password it was created
  with.
- `.env.example` keeps placeholders only.
- Generated values belong to one environment. Generate a new set for each
  environment (development, staging, production) and never copy one between
  them: run `create` on the target host, or store fresh values in the
  platform's secret manager.
- `scripts/check_env_secrets.py` (run by the test suite) fails when a secret
  that `docker-compose.yml`, `deploy/`, `api/settings/prod.py`, or
  `docker-entrypoint.sh` requires is missing from this list, and when Compose
  falls back to a published value for a secret.

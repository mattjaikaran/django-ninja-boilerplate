# Worktree dev stacks

Use `just wt-new` to run a second copy of the dev stack next to your main
checkout. Each worktree gets its own Compose project, its own host ports,
its own containers and volumes, and its own database. Two stacks can run at
the same time.

## Commands

|Command|Purpose|
|---|---|
|`just wt-new <branch> [base]`|Create branch `<branch>` (from `base`, default `HEAD`) and a worktree for it. Reuse the branch if it exists.|
|`just wt-ls`|List the main checkout and each worktree with its slot, project, database, ports, and running services. Report orphaned stacks.|
|`just wt-rm <branch>`|Stop and remove the worktree's stack, its volumes, its networks, and its database, then remove the worktree. Keep the branch.|

Run `just wt-new` from the main checkout. Each worktree then starts with its
own `.env`.

## What `wt-new` does

1. Creates the worktree in `WORKTREES_DIR` (default `../<repo>-worktrees`),
   where `<branch>` replaces `/` with `-`.
2. Assigns the next free slot `N` whose ports do not overlap another stack.
   Slot 0 is the main checkout.
3. Writes the worktree `.env` with:
   - `COMPOSE_PROJECT_NAME=<repo>-wt<N>` and `WT_SLOT=<N>`.
   - `DB_NAME=<main DB_NAME>_wt<N>`, such as `boilerplate_db_wt1`. See
     [Per-worktree database](#per-worktree-database).
   - Host ports offset by `100 * N`. The offset applies to every
     `*_PORT` value that the compose file publishes, plus `TEST_POSTGRES_PORT`
     and `TEST_VALKEY_PORT`.
   - `CSRF_TRUSTED_ORIGINS` and `MCP_BASE_URL` rewritten to the new Django
     port when they point at `localhost` or `127.0.0.1`.
   - `PORT` unchanged. Gunicorn binds `PORT` inside the container, so
     container networking does not depend on the host port.
   - `DB_HOST` and `DB_PORT` unchanged. Host commands still reach the local
     Postgres server on `127.0.0.1:5432`.
   - `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:<JAEGER_OTLP_GRPC_PORT>`
     when the main `.env` does not set it. Host processes send traces to this
     stack's Jaeger. Containers pin their own endpoint in Compose.
   - `CENTRIFUGO_URL` unchanged. Containers reach Centrifugo by service name.
     Host processes cannot resolve that name. Use `http://localhost:<CENTRIFUGO_PORT>`
     from the worktree `.env` for host-side publishing.
4. Runs `uv sync --extra dev` in the worktree.
5. Creates the database `<DB_NAME>_wt<N>` on the local Postgres server. It
   uses the main checkout's `.venv` and the main `DB_USER`, `DB_PASSWORD`,
   `DB_HOST`, and `DB_PORT`. It fails if the database already exists.
6. Runs `manage.py migrate` in the worktree against that database.
7. Runs `just pre-commit-install` from the main checkout. See
   [Git hooks](#git-hooks).

If a step after the worktree is created fails, `wt-new` keeps the worktree
and prints the `just wt-rm` command to clean it up.

Start the stack from the worktree with `just dev`. `just dev` moves any port
that is still busy to a free port at run time.

## Port layout

Slot `N` adds `100 * N` to each base port. Check the result with `just wt-ls`.

|Slot|Postgres|Valkey|Django|
|---|---|---|---|
|0 (main)|`POSTGRES_PORT` (5433)|`VALKEY_PORT` (6380)|`DJANGO_PORT` (8000)|
|1|5533|6480|8100|
|2|5633|6580|8200|

`wt-new` picks the lowest slot whose ports do not overlap the ports of slot 0
or of any existing worktree or leftover stack. It does not check ports used
by other projects on the host. `just dev` moves busy ports at run time, and
`just check-ports` lists them.

## Per-worktree database

Each worktree has its own database on the local Postgres server. `wt-new`
sets `DB_NAME=<DB_NAME>_wt<N>` in the worktree `.env`, creates that database,
and migrates it. For slot 1 with the default `DB_NAME`, that is
`boilerplate_db_wt1`. The main checkout keeps `boilerplate_db`, and no
worktree writes to it.

Host commands in a worktree read the worktree `DB_NAME`. This includes the
app-database probe in `doctor --check`, and `just wt-ls` shows the name in
its DATABASE column.

Compose sets the stack Postgres container's `POSTGRES_DB` from `DB_NAME`, so
the container creates a database with the same name in its own volume. That
container database is separate from the one on the local server. To migrate
it, run this from the worktree, with the stack's host port for `DB_PORT`:

```bash
DJANGO_SETTINGS_MODULE=api.settings.dev DB_POOL_ENABLED=false DB_HOST=127.0.0.1 DB_PORT=5533 uv run python manage.py migrate
```

Keep `DB_PORT=5432` in the worktree `.env`. Compose also reads that key to
set the container port, so a host port there breaks the stack containers.
Containers are not affected by the host database: Compose sets `DB_HOST=db`
for them.

Do not create other databases named `<DB_NAME>_wt<N>` by hand. `wt-new`
fails when the name exists, and `wt-rm` drops any database with that name
for the worktree.

## Remove a worktree stack

```bash
just wt-rm wt-test-a
```

`wt-rm`:

- Refuses to remove the main checkout.
- Refuses to remove a worktree with uncommitted changes. Commit or stash
  first.
- Refuses to stop a stack whose project name is not `<repo>-wt<N>`, such as
  the main project. Stop that stack by hand, then remove the worktree.
- Refuses to drop a database whose `DB_NAME` is neither the main `DB_NAME` nor
  `<main DB_NAME>_wt<N>`. Set `DB_NAME` in the worktree `.env`, then run the
  command again. Nothing is stopped or removed.
- Keeps the main checkout's database when the worktree `.env` names it. Older
  worktrees copied that name from the main `.env`. The removal still runs.
- Runs `docker compose --profile "*" down -v --remove-orphans` for the
  worktree project. The `-v` flag deletes that stack's volumes, including
  its Postgres data. Back up that data first if you need it.
- Runs `DROP DATABASE IF EXISTS` on the worktree's database on the local
  server. It does not force-disconnect other sessions. Close any client that
  uses that database first. A failed drop keeps the worktree.
- Runs `git worktree remove` without `--force`.
- Checks for leftover containers, volumes, and networks in the project. It
  fails if any remain.
- Keeps the branch. Delete it with `git branch -D <branch>` when the branch
  is merged or abandoned.

Do not run `git worktree remove` on a worktree that has a running stack. The
containers keep running, and `just wt-ls` reports them as orphaned. If that
happens, run the command that `wt-ls` prints from the main checkout.

## Git hooks

Git stores hooks in the shared `.git/hooks` directory, so every worktree uses
the same hooks. `just pre-commit-install` pins the hooks to the main
checkout's `.venv/bin/python`. Keep the main `.venv` in place. If you delete
it, run `just pre-commit-install` from the main checkout again.

`just doctor --check` warns when a hook points to a missing interpreter.

## Configuration

|Variable|Default|Purpose|
|---|---|---|
|`WORKTREES_DIR`|`../<repo>-worktrees`|Parent directory for `wt-new` worktrees. Set it in `.env` or the environment.|

Do not confuse `WORKTREES_DIR` with `WORKER_WORKTREES`. `WORKER_WORKTREES`
(default `~/worktrees/<repo>`) sets where the ticket worker creates its
per-ticket worktrees. See [AGENT_HANDOFF.md](AGENT_HANDOFF.md).

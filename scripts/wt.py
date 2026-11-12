#!/usr/bin/env python3
"""Create, list, and remove worktree dev stacks.

Each worktree gets one git worktree, one Compose project, and one block of
host ports. Slot N adds N * 100 to every host port of the main checkout's
.env. The main checkout is slot 0. Standard library only; run it from any
checkout of the repository. See docs/WORKTREES.md.

Usage:
    python3 scripts/wt.py new BRANCH [BASE]
    python3 scripts/wt.py rm BRANCH_OR_PATH
    python3 scripts/wt.py ls
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dev_ports

SLOT_STRIDE = 100
# Ports that Compose does not publish but the test recipes read from .env.
EXTRA_PORTS = {"TEST_POSTGRES_PORT": 5434, "TEST_VALKEY_PORT": 6381}
# gunicorn binds PORT inside the container, so the offset must not change it.
NEVER_OFFSET = frozenset({"PORT"})
URL_KEYS = ("CSRF_TRUSTED_ORIGINS", "MCP_BASE_URL")
STACK_PORT_KEYS = ("POSTGRES_PORT", "VALKEY_PORT", "DJANGO_PORT")
SHORT_TIMEOUT = 60
LONG_TIMEOUT = 900
PS_STACK_FORMAT = (
    '{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}'
)
PROJECT_LABEL = "com.docker.compose.project"
DB_SCRIPT = """
import os
import sys

import psycopg
from psycopg import sql

action, name = sys.argv[1], sys.argv[2]
conn = psycopg.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dbname="postgres",
    autocommit=True,
)
with conn, conn.cursor() as cur:
    if action == "create":
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        if cur.fetchone():
            sys.exit(f"database {name} already exists")
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    else:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
"""


class StackError(Exception):
    """A step failed. The message tells the user what to do next."""


class Worktree(NamedTuple):
    path: Path
    branch: str | None


def run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = SHORT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run a command; a missing binary or a timeout returns a failed result."""
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(cmd, 127, "", str(error))


def must(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = SHORT_TIMEOUT,
) -> str:
    """Run a command and return its stdout, or raise StackError."""
    result = run(cmd, cwd=cwd, env=env, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        reason = detail[-1] if detail else "no output"
        raise StackError(f"{' '.join(cmd)} failed: {reason}")
    return result.stdout


def docker(*args: str, strict: bool = False) -> list[str]:
    """Non-empty output lines of a docker command; [] on failure unless strict."""
    result = run(["docker", *args])
    if result.returncode != 0:
        if strict:
            detail = result.stderr.strip().splitlines()
            reason = detail[-1] if detail else "no output"
            raise StackError(f"docker {' '.join(args)} failed: {reason}")
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def main_root() -> Path:
    """The main checkout, which holds the shared git common directory."""
    common = must(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path.cwd(),
    ).strip()
    return Path(common).parent


def worktrees(root: Path) -> list[Worktree]:
    """Every worktree of the repository; the main checkout comes first."""
    listing = must(["git", "worktree", "list", "--porcelain"], cwd=root)
    entries: list[Worktree] = []
    path: Path | None = None
    branch: str | None = None
    for line in [*listing.splitlines(), ""]:
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/") :]
        elif not line and path is not None:
            entries.append(Worktree(path, branch))
            path, branch = None, None
    return entries


def compose_text(root: Path) -> str:
    return (root / dev_ports.COMPOSE_FILE).read_text()


def main_env(root: Path) -> dict[str, str]:
    if not (root / dev_ports.ENV_FILE).is_file():
        raise StackError("no .env in the main checkout; run: just setup-env")
    return dev_ports.load_env(root / dev_ports.ENV_FILE)


def port_defaults(text: str) -> dict[str, int]:
    """Host port variables of every Compose service, with their defaults."""
    defaults = {
        var.name: var.default
        for var in dev_ports.parse_compose(text, None)
        if var.name not in NEVER_OFFSET
    }
    defaults.update(EXTRA_PORTS)
    return defaults


def base_port(name: str, default: int, env: dict[str, str]) -> int:
    """The main checkout's port for ``name``, else the default."""
    value = env.get(name, "")
    return int(value) if value.isdigit() else default


def slot_ports(
    defaults: dict[str, int], env: dict[str, str], slot: int
) -> dict[str, str]:
    return {
        name: str(base_port(name, default, env) + SLOT_STRIDE * slot)
        for name, default in defaults.items()
    }


def rewrite_urls(env: dict[str, str], moved: dict[int, int]) -> dict[str, str]:
    """Move the localhost ports in URL settings to their new values."""
    pattern = re.compile(r"(https?://(?:localhost|127\.0\.0\.1)):(\d+)\b")
    rewritten: dict[str, str] = {}
    for key in URL_KEYS:
        if key in env:
            rewritten[key] = pattern.sub(
                lambda m: f"{m.group(1)}:{moved.get(int(m.group(2)), int(m.group(2)))}",
                env[key],
            )
    return rewritten


def set_values(text: str, values: dict[str, str]) -> str:
    """Set ``values`` in dotenv ``text``, keeping every other line."""
    seen: set[str] = set()
    lines: list[str] = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in values:
            lines.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            lines.append(line)
    missing = [key for key in values if key not in seen]
    if missing:
        lines += ["", "# Worktree stack values, written by scripts/wt.py"]
        lines += [f"{key}={values[key]}" for key in missing]
    return "\n".join(lines) + "\n"


def write_private(path: Path, text: str) -> None:
    """Write ``path`` atomically with mode 0600; it holds secrets."""
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    tmp.replace(path)


def worktrees_dir(root: Path, env: dict[str, str]) -> Path:
    raw = os.environ.get("WORKTREES_DIR") or env.get("WORKTREES_DIR")
    raw = raw or f"../{root.name}-worktrees"
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (root / path).resolve()


def next_slot(
    root: Path, project: str, defaults: dict[str, int], env: dict[str, str]
) -> int:
    """The lowest slot with no leftover resources and no overlapping ports."""
    used: set[int] = set()
    for wt in worktrees(root):
        raw = dev_ports.load_env(wt.path / dev_ports.ENV_FILE).get("WT_SLOT", "")
        if raw.isdigit():
            used.add(int(raw))
    pattern = re.compile(rf"^{re.escape(project)}-wt(\d+)(?:$|[_-])")
    names = [
        line.partition("\t")[0]
        for line in docker("ps", "-a", "--format", PS_STACK_FORMAT)
    ]
    names += docker("volume", "ls", "--format", "{{.Name}}")
    for name in names:
        if match := pattern.match(name):
            used.add(int(match.group(1)))
    taken: set[str] = set()
    for slot in used | {0}:
        taken.update(slot_ports(defaults, env, slot).values())
    number = 1
    while number in used or taken & set(slot_ports(defaults, env, number).values()):
        number += 1
    return number


def main_db_name(env: dict[str, str]) -> str:
    """The main checkout's database name. Compose defaults to boilerplate_db."""
    return env.get("DB_NAME") or "boilerplate_db"


def db_env(env: dict[str, str], db_name: str) -> dict[str, str]:
    """Pin the DB_* keys from .env, so an exported shell value cannot override them."""
    pinned: dict[str, str] = {
        key: env[key]
        for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD")
        if key in env
    }
    pinned["DB_NAME"] = db_name
    return pinned


def db_admin(root: Path, action: str, name: str, env: dict[str, str]) -> None:
    """Create or drop a database on the host Postgres, via the main venv's psycopg."""
    result = run(
        [
            "uv",
            "run",
            "--no-sync",
            "--project",
            str(root),
            "python",
            "-c",
            DB_SCRIPT,
            action,
            name,
        ],
        cwd=root,
        env={**os.environ, **db_env(env, name)},
        timeout=SHORT_TIMEOUT,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        reason = detail[-1] if detail else "no output"
        host = f"{env.get('DB_HOST', '')}:{env.get('DB_PORT', '')}"
        raise StackError(f"could not {action} database {name} on {host}: {reason}")


def cmd_new(branch: str, base: str) -> None:
    root = main_root()
    env = main_env(root)
    if run(["git", "check-ref-format", "--branch", branch], cwd=root).returncode != 0:
        raise StackError(f"not a valid branch name: {branch}")
    base = base or "HEAD"
    path = worktrees_dir(root, env) / branch.replace("/", "-")
    if path.exists():
        raise StackError(f"path already exists: {path}")
    has_branch = (
        run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root
        ).returncode
        == 0
    )
    if has_branch and base != "HEAD":
        raise StackError(f"branch {branch} exists; BASE applies only to new branches")

    project = dev_ports.project_name(root, compose_text(root), env)
    defaults = port_defaults(compose_text(root))
    slot = next_slot(root, project, defaults, env)
    stack = f"{project}-wt{slot}"
    db_name = f"{main_db_name(env)}_wt{slot}"
    ports = slot_ports(defaults, env, slot)
    moved = {
        base_port(name, default, env): int(ports[name])
        for name, default in defaults.items()
        if int(ports[name]) != base_port(name, default, env)
    }
    values = {
        "COMPOSE_PROJECT_NAME": stack,
        "WT_SLOT": str(slot),
        "DB_NAME": db_name,
        **ports,
        **rewrite_urls(env, moved),
    }
    if "OTEL_EXPORTER_OTLP_ENDPOINT" not in env:
        # Host processes read this key; app containers pin their own endpoint.
        values["OTEL_EXPORTER_OTLP_ENDPOINT"] = (
            f"http://localhost:{ports['JAEGER_OTLP_GRPC_PORT']}"
        )

    if has_branch:
        add_cmd = ["git", "worktree", "add", str(path), branch]
    else:
        add_cmd = ["git", "worktree", "add", "-b", branch, str(path), base]
    must(add_cmd, cwd=root)
    try:
        write_private(
            path / dev_ports.ENV_FILE,
            set_values((root / dev_ports.ENV_FILE).read_text(), values),
        )
        must(["uv", "sync", "--extra", "dev"], cwd=path, timeout=LONG_TIMEOUT)
        db_admin(root, "create", db_name, env)
        migrate_env = {
            **os.environ,
            **db_env(env, db_name),
            "DJANGO_SETTINGS_MODULE": "api.settings.dev",
            "DB_POOL_ENABLED": "false",
        }
        must(
            ["uv", "run", "python", "manage.py", "migrate"],
            cwd=path,
            env=migrate_env,
            timeout=LONG_TIMEOUT,
        )
        # Hooks are shared across worktrees, so pin them from the main checkout.
        must(["just", "pre-commit-install"], cwd=root, timeout=LONG_TIMEOUT)
    except StackError as error:
        raise StackError(
            f"{error}\nWorktree kept at {path}. Fix the step above, "
            f"or remove it with: just wt-rm {branch}"
        ) from error

    print(f"Created {branch} at {path}")
    print(f"  project {stack}, slot {slot}")
    print(f"  database {db_name}")
    print(
        "  ports "
        + ", ".join(f"{key}={ports[key]}" for key in STACK_PORT_KEYS if key in ports)
    )
    print(f"Start it with: cd {path} && just dev")


def cmd_rm(target: str) -> None:
    root = main_root()
    main_path = root.resolve()
    matches = [
        wt
        for wt in worktrees(root)
        if wt.branch == target
        or wt.path.resolve() == Path(target).expanduser().resolve()
    ]
    if not matches:
        raise StackError(f"no worktree for branch or path: {target}")
    wt = matches[0]
    if wt.path.resolve() == main_path:
        raise StackError("refusing to remove the main checkout")
    if must(["git", "status", "--porcelain"], cwd=wt.path).strip():
        raise StackError(
            f"{wt.path} has uncommitted changes; commit or stash them first"
        )

    project = ""
    db_name = ""
    if (wt.path / dev_ports.ENV_FILE).is_file():
        wt_env = dev_ports.load_env(wt.path / dev_ports.ENV_FILE)
        project = wt_env.get("COMPOSE_PROJECT_NAME", "")
        db_name = wt_env.get("DB_NAME", "")
        main_db = main_db_name(main_env(root))
        if (
            db_name
            and db_name != main_db
            and not re.fullmatch(rf"{re.escape(main_db)}_wt\d+", db_name)
        ):
            raise StackError(
                f"{wt.path} sets DB_NAME={db_name}, which is neither the main "
                f"database ({main_db}) nor a worktree database ({main_db}_wt<N>). "
                "Refusing to stop this stack or drop that database. Set DB_NAME "
                "in its .env, then run this command again."
            )
        if project:
            base = dev_ports.project_name(root, compose_text(root), main_env(root))
            if not re.fullmatch(rf"{re.escape(base)}-wt\d+", project):
                raise StackError(
                    f"{wt.path} sets COMPOSE_PROJECT_NAME={project}, which is not "
                    "a worktree stack. Refusing to stop it. Stop that stack by hand, "
                    f"then remove the worktree with: git worktree remove {wt.path}"
                )
            down_env = {**os.environ, "COMPOSE_PROJECT_NAME": project}
            down = run(
                [
                    "docker",
                    "compose",
                    "--profile",
                    "*",
                    "down",
                    "-v",
                    "--remove-orphans",
                ],
                cwd=wt.path,
                env=down_env,
                timeout=LONG_TIMEOUT,
            )
            if down.returncode != 0:
                detail = (down.stderr or down.stdout).strip().splitlines()
                reason = detail[-1] if detail else "no output"
                raise StackError(f"docker compose down failed; worktree kept: {reason}")
        if db_name == main_db:
            print(f"Kept database {db_name}; the main checkout uses it.")
        elif db_name:
            try:
                db_admin(root, "drop", db_name, main_env(root))
            except StackError as error:
                raise StackError(f"{error}; worktree kept") from error
            print(f"Dropped database {db_name}.")

    must(["git", "worktree", "remove", str(wt.path)], cwd=root)

    if project:
        leftovers: list[str] = []
        label = f"label={PROJECT_LABEL}={project}"
        leftovers += docker(
            "ps",
            "-a",
            "--filter",
            label,
            "--format",
            "container {{.Names}}",
            strict=True,
        )
        leftovers += docker(
            "volume",
            "ls",
            "--filter",
            label,
            "--format",
            "volume {{.Name}}",
            strict=True,
        )
        leftovers += docker(
            "network",
            "ls",
            "--filter",
            label,
            "--format",
            "network {{.Name}}",
            strict=True,
        )
        if leftovers:
            raise StackError(
                f"{project} still has resources:\n  " + "\n  ".join(leftovers)
            )
        print(
            f"Removed {wt.path}; no containers, volumes, or networks remain for {project}."
        )
    else:
        print(f"Removed {wt.path}; it had no .env, so no Compose stack was checked.")
    if wt.branch:
        print(
            f"The branch {wt.branch} was kept. Delete it with: git branch -D {wt.branch}"
        )


def cmd_ls() -> None:
    root = main_root()
    env = main_env(root)
    text = compose_text(root)
    base = dev_ports.project_name(root, text, env)
    defaults = port_defaults(text)
    running: dict[str, list[str]] = {}
    for line in docker("ps", "--format", PS_STACK_FORMAT):
        project, _, service = line.partition("\t")
        running.setdefault(project, []).append(service)
    stack_names = {
        line.partition("\t")[0]
        for line in docker("ps", "-a", "--format", PS_STACK_FORMAT)
    }
    stack_names |= set(docker("volume", "ls", "--format", "{{.Name}}"))

    # Each row: branch, slot, project, port values, and path.
    rows = [
        (
            "main",
            "0",
            base,
            {**slot_ports(defaults, env, 0), "DB_NAME": main_db_name(env)},
            str(root),
        )
    ]
    known = {base}
    for wt in worktrees(root):
        if wt.path.resolve() == root.resolve():
            continue
        wt_env = dev_ports.load_env(wt.path / dev_ports.ENV_FILE)
        project = wt_env.get("COMPOSE_PROJECT_NAME", "-")
        known.add(project)
        rows.append(
            (
                wt.branch or "(detached)",
                wt_env.get("WT_SLOT", "-"),
                project,
                wt_env,
                str(wt.path),
            )
        )

    print(
        f"{'BRANCH':<24} {'SLOT':<4} {'PROJECT':<32} {'DATABASE':<28} "
        f"{'PG':>6} {'VALKEY':>6} {'DJANGO':>6}  SERVICES"
    )
    for branch, slot, project, values, path in rows:
        services = ",".join(sorted(running.get(project, []))) or "none"
        print(
            f"{branch:<24} {slot:<4} {project:<32} {values.get('DB_NAME', '-'):<28} "
            f"{values.get('POSTGRES_PORT', '-'):>6} "
            f"{values.get('VALKEY_PORT', '-'):>6} {values.get('DJANGO_PORT', '-'):>6}  "
            f"{services}  {path}"
        )

    pattern = re.compile(rf"^({re.escape(base)}-wt\d+)(?:$|[_-])")
    orphans = set()
    for name in stack_names:
        match = pattern.match(name)
        if match and match.group(1) not in known:
            orphans.add(match.group(1))
    for project in sorted(orphans):
        print(
            f"Orphaned stack {project} has no worktree. Remove it from the main "
            f"checkout with:\n  COMPOSE_PROJECT_NAME={project} "
            "docker compose --profile '*' down -v --remove-orphans"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage worktree dev stacks.")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="create a worktree stack")
    new.add_argument("branch")
    new.add_argument("base", nargs="?", default="HEAD")
    rm = commands.add_parser("rm", help="remove a worktree stack")
    rm.add_argument("target")
    commands.add_parser("ls", help="list worktree stacks")
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            cmd_new(args.branch, args.base)
        elif args.command == "rm":
            cmd_rm(args.target)
        else:
            cmd_ls()
    except StackError as error:
        print(f"wt: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

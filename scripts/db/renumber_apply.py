"""Write, verify, roll back and commit a renumber (used by renumber_migrations.py)."""

from __future__ import annotations

import subprocess
import sys
import time
import uuid

import check_migrations as cm

ROOT = cm.ROOT
COMMIT_MESSAGE = "fix(migrations): Renumber after main"
MIGRATE_TIMEOUT = 1800  # seconds; a from-zero migrate took 4.5 min on 2026-11-06


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if check and proc.returncode != 0:
        sys.exit(
            f"renumber: git {' '.join(args[:3])} failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def commit_moves(moves: dict[str, tuple[str, str]]) -> None:
    """Commit the renames and rewrites, and nothing else that is staged."""
    new_paths = {n for n, _ in moves.values()}
    git("add", "--", *new_paths)
    in_head = [
        o
        for o in moves
        if subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{o}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    ]
    git(
        "commit",
        "-q",
        "-m",
        COMMIT_MESSAGE,
        "--",
        *dict.fromkeys([*in_head, *new_paths]),
    )


def rollback(
    moves: dict[str, tuple[str, str]], texts: dict[str, str], tracked: set[str]
) -> None:
    """Undo apply_moves: delete the new files, restore the old ones and the index."""
    for old, (new, _) in moves.items():
        if new != old:
            if old in tracked:
                git("rm", "-q", "-f", "--cached", "--ignore-unmatch", "--", new)
            (ROOT / new).unlink(missing_ok=True)
    for old in moves:
        (ROOT / old).write_text(texts[old], encoding="utf-8")
        if old in tracked:
            git("add", "--", old)


def apply_moves(moves: dict[str, tuple[str, str]]) -> set[str]:
    """Write all new files after removing all old ones (a new name can equal
    another own file's old name). A path on the base is never written."""
    tracked = set(git("ls-files", "--", *moves).split())
    for old, (new, _) in moves.items():
        if new != old and (ROOT / new).exists() and new not in moves:
            sys.exit(f"renumber: {new} already exists; refusing to overwrite it")
    for old, (new, _) in moves.items():
        if new != old:
            if old in tracked:
                git("rm", "-q", "-f", "--cached", "--", old)
            (ROOT / old).unlink()
    for old, (new, text) in moves.items():
        (ROOT / new).write_text(text, encoding="utf-8")
        if old in tracked:
            git("add", "--", new)
        print(f"  wrote {new}")
    return tracked


def verify(skip_migrate: bool) -> int:
    print("verify: makemigrations --check --dry-run")
    problems = cm.check_leaf()
    if problems:
        print("\n".join(problems))
        return 1
    if skip_migrate:
        return 0
    return migrate_scratch()


def migrate_scratch() -> int:
    """Run a real `migrate` on a throwaway Postgres container."""
    name = f"renumber-pg-{uuid.uuid4().hex[:8]}"
    run = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=postgres",
         "-e", "POSTGRES_DB=test_db", "-p", "127.0.0.1::5432", "postgres:17-alpine"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if run.returncode != 0:
        print(f"verify: cannot start a scratch Postgres: {run.stderr.strip()}")
        return 1
    try:
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "test_db"],
                capture_output=True, check=False,
            )  # fmt: skip
            if ready.returncode == 0:
                break
            time.sleep(1)
        time.sleep(2)  # the entrypoint restarts the server once after init
        port = (
            subprocess.run(
                ["docker", "port", name, "5432/tcp"],
                capture_output=True,
                text=True,
                check=False,
            )
            .stdout.split(":")[-1]
            .strip()
        )
        env = {
            **cm.django_env(),
            **cm.SCRATCH_ENV,
            "DB_HOST": "127.0.0.1",
            "DB_PORT": port,
        }
        print(f"verify: migrate on scratch Postgres {name} (port {port})")
        try:
            proc = cm.manage("migrate", "--noinput", env=env, timeout=MIGRATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"verify: migrate did not finish in {MIGRATE_TIMEOUT} s")
            return 1
        if proc.returncode != 0:
            print((proc.stdout + proc.stderr)[-3000:])
            return 1
        print("verify: migrate ok")
        return 0
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)

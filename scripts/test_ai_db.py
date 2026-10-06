#!/usr/bin/env python3
"""Run the Postgres-only tests on a throwaway pgvector Postgres container.

The default suite runs on SQLite without ``core.ai``, so the owner-scoped
``hybrid_search`` and graph walk tests and the concurrent-refresh test (row
locks) skip there. This script starts ``pgvector/pgvector:pg17`` on a free
loopback port, runs those tests with ``AI_ENABLED=true``, fails if any of them
skips, and removes the container.

Exit codes: 0 pass, 1 test failure, 2 Docker or Postgres unavailable.

Usage:
    python scripts/test_ai_db.py [extra pytest args]
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid

IMAGE = "pgvector/pgvector:pg17"
TESTS = [
    "core/tests/test_ai_helpers.py",
    "core/tests/test_token_refresh.py::"
    "test_concurrent_refresh_of_one_token_keeps_the_session",
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(name: str, timeout_s: float = 60) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        ready = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-U", "postgres", "-h", "127.0.0.1"],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return True
        time.sleep(1)
    return False


def main(argv: list[str]) -> int:
    name = f"ai-db-tests-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    started = subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_PASSWORD=postgres", "-e", "POSTGRES_DB=test_db",
            "-p", f"127.0.0.1:{port}:5432", IMAGE,
        ],
        capture_output=True,
        text=True,
        check=False,
    )  # fmt: skip
    if started.returncode != 0:
        print(f"Cannot start {IMAGE}: {started.stderr.strip()}", file=sys.stderr)
        return 2
    try:
        if not _wait_ready(name):
            print("pgvector container did not become ready", file=sys.stderr)
            return 2
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "api.settings.test",
            "AI_ENABLED": "true",
            "CI": "1",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": str(port),
            "DB_NAME": "test_db",
            "DB_USER": "postgres",
            "DB_PASSWORD": "postgres",
        }
        # The TEST gate's extras plus `ai`, so this run does not re-sync .venv
        # away from the packages the other gates need.
        command = [
            "uv", "run", "--extra", "dev", "--extra", "huey", "--extra", "django-q",
            "--extra", "django-rq", "--extra", "dramatiq", "--extra", "ai",
            "pytest", "--no-cov", "--create-db", "-p", "no:cacheprovider",
            "-rs", "-v", *TESTS, *argv,
        ]  # fmt: skip
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, check=False
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            return 1
        # A skip here means the DB setup is wrong, not that the code is fine.
        if " skipped" in result.stdout.splitlines()[-1]:
            print("AI tests skipped on the pgvector database", file=sys.stderr)
            return 1
        return 0
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

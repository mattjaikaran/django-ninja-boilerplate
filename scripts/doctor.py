#!/usr/bin/env python3
"""Agent and developer preflight for the Django Ninja Boilerplate.

Each check prints one line: OK, INFO, WARN, or FAIL, with a fix hint.
The script never prints secret values; it names keys only.

Exit codes: 0 when no check fails, 1 when at least one check fails.

Usage:
    ./scripts/doctor.sh
    python3 scripts/doctor.py
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLORS = {"OK": "32", "INFO": "34", "WARN": "33", "FAIL": "31"}
counts = dict.fromkeys(COLORS, 0)


def report(level: str, message: str, hint: str = "") -> None:
    counts[level] += 1
    label = f"{level:<4}"
    if sys.stdout.isatty():
        label = f"\033[{COLORS[level]}m{label}\033[0m"
    suffix = f"  -> {hint}" if hint else ""
    print(f"[{label}] {message}{suffix}")


def run(
    args: list[str], timeout: float = 10
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def check_tools() -> None:
    version = sys.version_info
    if version >= (3, 11):
        report("OK", f"Python {version.major}.{version.minor}.{version.micro}")
    else:
        report(
            "FAIL", f"Python {version.major}.{version.minor} is too old", "use 3.11+"
        )
    for tool, hint in (
        ("uv", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
        ("just", "brew install just"),
    ):
        if shutil.which(tool):
            report("OK", f"{tool} found")
        else:
            report("FAIL", f"{tool} not found", hint)
    if shutil.which("git"):
        report("OK", "git found")
    else:
        report("WARN", "git not found", "install git")
    if not shutil.which("docker"):
        report(
            "INFO",
            "docker not installed",
            "needed only for `just up` and Postgres tests",
        )
        return
    info = run(["docker", "info"], timeout=15)
    if info is not None and info.returncode == 0:
        report("INFO", "Docker daemon is up")
    else:
        report("INFO", "Docker daemon is down", "start Docker Desktop for `just up`")
    compose = run(["docker", "compose", "version"])
    if compose is None or compose.returncode != 0:
        report("WARN", "docker compose plugin not found", "install Docker Compose v2")


def check_ci_var() -> None:
    if os.environ.get("CI"):
        report(
            "WARN",
            "CI is set in the environment; it no longer changes the test DB",
            "use TEST_DB=postgres to test on PostgreSQL; unset CI to silence",
        )
    else:
        report("OK", "CI is not set")


def check_env_files(env: dict[str, str]) -> None:
    if not (ROOT / ".env").is_file():
        report("FAIL", ".env not found", "run: just setup-env")
        return
    report("OK", ".env exists")
    missing = [
        k for k in ("SECRET_KEY", "DB_NAME", "DB_USER", "DB_PASSWORD") if k not in env
    ]
    if missing:
        report(
            "WARN",
            f".env is missing keys: {', '.join(missing)}",
            "copy them from .env.example",
        )
    dev_path = ROOT / ".env.development"
    if dev_path.is_file():
        dev = parse_env(dev_path)
        differ = [
            k
            for k in ("DB_HOST", "DB_PORT")
            if k in env and k in dev and env[k] != dev[k]
        ]
        if differ:
            report(
                "WARN",
                f".env and .env.development differ on: {', '.join(differ)}",
                "align them so manage.py and the Docker stack hit the same DB",
            )
        else:
            report("OK", "DB_HOST/DB_PORT agree between .env and .env.development")
    check_secrets()


def check_secrets() -> None:
    """FAIL on unset secrets (Compose refuses to start), WARN on weak ones."""
    if not (ROOT / "scripts" / "env_secrets.py").is_file():
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    import env_secrets

    current = env_secrets.read_env(ROOT / ".env")
    unset = [
        s.name
        for s in env_secrets.SECRETS
        if env_secrets.is_unset(s, current.get(s.name))
    ]
    weak = [n for n in env_secrets.weak_secrets(ROOT / ".env") if n not in unset]
    hint = "run: python3 scripts/env_secrets.py fill"
    if unset:
        report("FAIL", f"unset secrets in .env: {', '.join(unset)}", hint)
    if weak:
        report("WARN", f"weak secrets in .env: {', '.join(weak)}", hint)
    if not unset and not weak:
        report("OK", f"all {len(env_secrets.SECRETS)} generated secrets are set")


def port_owner(port: int) -> str:
    if not shutil.which("lsof"):
        return ""
    result = run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], timeout=5)
    if result is None or result.returncode != 0:
        return ""
    rows = result.stdout.splitlines()[1:]
    if not rows:
        return ""
    fields = rows[0].split()
    return f" by {fields[0]} (pid {fields[1]})" if len(fields) > 1 else ""


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def check_ports(env: dict[str, str]) -> None:
    def setting(key: str, default: str) -> int:
        value = os.environ.get(key) or env.get(key) or default
        return int(value) if value.isdigit() else int(default)

    for name, key, default in (
        ("Postgres", "POSTGRES_PORT", "5433"),
        ("Valkey", "VALKEY_PORT", "6380"),
        ("Django", "DJANGO_PORT", "8000"),
        ("Flower", "FLOWER_PORT", "5555"),
    ):
        port = setting(key, default)
        if port_busy(port):
            report(
                "WARN",
                f"{name} port {port} is in use{port_owner(port)}",
                f"`just dev` moves {key} to a free port; `just check-ports` shows it",
            )
        else:
            report("OK", f"{name} port {port} is free")

    check_services(
        setting("POSTGRES_PORT", "5433"),
        setting("VALKEY_PORT", "6380"),
        setting("DJANGO_PORT", "8000"),
    )


def check_services(pg_port: int, valkey_port: int, django_port: int) -> None:
    """Probe the running stack; a stopped stack is INFO, not a failure."""
    for name, port in (("Postgres", pg_port), ("Valkey", valkey_port)):
        if port_busy(port):
            report("INFO", f"{name} accepts connections on 127.0.0.1:{port}")
        else:
            report(
                "INFO", f"{name} not reachable on 127.0.0.1:{port}", "start it: just up"
            )
    url = f"http://127.0.0.1:{django_port}/api/health/"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            report("OK", f"Django health endpoint returned {response.status}")
    except (OSError, ValueError):
        report(
            "INFO",
            f"Django health endpoint not responding at {url}",
            "start it: just dev",
        )


def check_project_files() -> None:
    for name in (".env.example", "pyproject.toml", "Dockerfile", "docker-compose.yml"):
        if (ROOT / name).is_file():
            report("OK", f"{name} exists")
        else:
            level = "WARN" if name == ".env.example" else "FAIL"
            report(level, f"{name} not found", "restore it from git")


def check_workspace() -> None:
    journeys = os.environ.get("JOURNEYS_E2E_DIR")
    if journeys and Path(journeys).is_dir():
        report("INFO", f"journeys frontend found at {journeys}")
    elif journeys:
        report("INFO", f"JOURNEYS_E2E_DIR={journeys} does not exist", "fix the path")
    else:
        report("INFO", "JOURNEYS_E2E_DIR not set; journey E2E tests will skip")
    status = run(["git", "status", "--porcelain"])
    if status is not None and status.returncode == 0:
        changed = len(status.stdout.splitlines())
        report(
            "INFO",
            f"git tree has {changed} changed path(s)" if changed else "git tree clean",
        )
    cores = os.cpu_count() or 1
    try:
        load = os.getloadavg()[0]
    except OSError:
        return
    if load > cores:
        report(
            "WARN",
            f"load {load:.1f} exceeds {cores} cores",
            "expect slow, flaky test runs",
        )
    else:
        report("OK", f"load {load:.1f} on {cores} cores")


def main() -> int:
    env = parse_env(ROOT / ".env")
    print("Django Ninja Boilerplate doctor")
    check_tools()
    check_ci_var()
    check_env_files(env)
    check_project_files()
    check_ports(env)
    check_workspace()
    summary = ", ".join(f"{counts[k]} {k}" for k in ("OK", "INFO", "WARN", "FAIL"))
    print(f"Summary: {summary}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

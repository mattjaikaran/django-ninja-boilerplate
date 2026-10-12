#!/usr/bin/env python3
"""Find free host ports for the dev Compose stack.

The dev services publish host ports in the form ``${VAR:-default}`` in
``docker-compose.yml`` (``POSTGRES_PORT``, ``VALKEY_PORT``, ``DJANGO_PORT``).
This script reads those ports for the selected profiles, takes each value from
the environment, then ``.env``, then the Compose default, and tries to bind it.
A port that a running container of this Compose project publishes counts as
free, so a running stack keeps its ports. For each busy port it picks the next
free port upward.

``--check`` prints a report and exits 1 when a port is busy. ``--env`` prints
only ``VAR=port`` lines for the busy ports, for ``export $(...)``. ``--port
VAR`` prints the one port ``just dev`` uses for ``VAR``. Other scripts import
:func:`resolve_ports`.
The script uses the Python standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from env_secrets import read_env

COMPOSE_FILE = "docker-compose.yml"
ENV_FILE = ".env"
DEFAULT_BIND_ADDRESS = "127.0.0.1"
MAX_PORT = 65535
# The host side of a published port: "${VAR:-1234}:" (a bind address
# variable such as ${DEV_BIND_ADDRESS:-127.0.0.1} does not match).
_HOST_PORT = re.compile(r"\$\{([A-Z][A-Z0-9_]*):-(\d+)\}:\d")
_SERVICE = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
_KEY = re.compile(r"^    ([a-z_]+):")
_LIST_ITEM = re.compile(r"^\s+-\s+\"?([^\"#\s]+)")
# Published host ports in `docker ps` output: "0.0.0.0:5433->5432/tcp" or a
# range "0.0.0.0:8000-8001->8000-8001/tcp".
_PUBLISHED = re.compile(r":(\d+)(?:-(\d+))?->")


class PortVar(NamedTuple):
    """One host port variable published by a Compose service."""

    name: str
    default: int
    service: str


class Result(NamedTuple):
    """The check result for one port variable."""

    var: PortVar
    port: int
    free_port: int

    @property
    def busy(self) -> bool:
        """True when the configured port is taken."""
        return self.free_port != self.port


def parse_compose(text: str, profiles: set[str]) -> list[PortVar]:
    """Return the ``${VAR:-default}`` host ports of services in ``profiles``.

    Reads the two-space service layout of ``docker-compose.yml`` line by line,
    so no YAML library is needed.
    """
    found: dict[str, tuple[set[str], list[PortVar]]] = {}
    service: str | None = None
    section: str | None = None
    in_services = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            in_services = line.startswith("services:")
            service = None
            continue
        if not in_services:
            continue
        if match := _SERVICE.match(line):
            service, section = match.group(1), None
            found[service] = (set(), [])
            continue
        if service is None:
            continue
        if match := _KEY.match(line):
            section = match.group(1)
            continue
        service_profiles, ports = found[service]
        if section == "profiles" and (item := _LIST_ITEM.match(line)):
            service_profiles.add(item.group(1))
        elif section == "ports":
            for name, default in _HOST_PORT.findall(line):
                ports.append(PortVar(name, int(default), service))
    result: list[PortVar] = []
    seen: set[str] = set()
    for service_profiles, ports in found.values():
        if not service_profiles & profiles:
            continue
        for var in ports:
            if var.name not in seen:
                seen.add(var.name)
                result.append(var)
    return result


def load_env(path: Path) -> dict[str, str]:
    """Return the ``.env`` values Compose interpolates, or {} without a file."""
    return read_env(path) if path.is_file() else {}


def setting(name: str, dotenv: dict[str, str], default: str) -> str:
    """Return ``name`` from the environment, then ``.env``, then ``default``.

    This is the order Compose uses for interpolation.
    """
    return os.environ.get(name) or dotenv.get(name) or default


def project_name(root: Path, compose_text: str, dotenv: dict[str, str]) -> str:
    """Return the Compose project name, normalized the way Compose does it."""
    name = os.environ.get("COMPOSE_PROJECT_NAME") or dotenv.get("COMPOSE_PROJECT_NAME")
    if not name and (
        match := re.search(r"^name:\s*\"?([^\"\s#]+)", compose_text, re.MULTILINE)
    ):
        name = match.group(1)
    name = (name or root.resolve().name).lower()
    return re.sub(r"[^a-z0-9_-]", "", name)


def project_ports(project: str) -> set[int]:
    """Return the host ports that running containers of ``project`` publish.

    Returns an empty set when Docker is missing or not running. Uses
    ``docker ps`` rather than ``docker compose ps``: Compose would interpolate
    the compose file, which fails while a guarded secret is unset.
    """
    command = [
        "docker",
        "ps",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--format",
        "{{.Ports}}",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if completed.returncode != 0:
        return set()
    ports: set[int] = set()
    for first, last in _PUBLISHED.findall(completed.stdout):
        ports.update(range(int(first), int(last or first) + 1))
    return ports


def is_free(port: int, address: str) -> bool:
    """Return True when ``address:port`` can be bound.

    No SO_REUSEADDR: with it, macOS lets you bind 127.0.0.1 next to a
    0.0.0.0 listener, which would report a port that Docker publishes as free.
    """
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((address, port))
        except OSError:
            return False
    return True


def check_ports(
    variables: list[PortVar],
    values: dict[str, int],
    address: str,
    own: set[int],
) -> list[Result]:
    """Find a free port for each variable, starting at its configured value.

    Ports in ``own`` count as free. Two variables never get the same port.
    """
    claimed: set[int] = set()
    results: list[Result] = []

    def available(port: int) -> bool:
        return port not in claimed and (port in own or is_free(port, address))

    for var in variables:
        port = values[var.name]
        candidate = port
        while candidate <= MAX_PORT and not available(candidate):
            candidate += 1
        if candidate > MAX_PORT:
            raise RuntimeError(f"no free port at or above {port} for {var.name}")
        claimed.add(candidate)
        results.append(Result(var, port, candidate))
    return results


class Resolution(NamedTuple):
    """The ports ``just dev`` would publish, from :func:`resolve_ports`."""

    address: str
    """The host bind address (``DEV_BIND_ADDRESS``)."""
    own: set[int]
    """Host ports that running containers of this Compose project publish."""
    results: list[Result]


def resolve_ports(root: Path, profiles: set[str]) -> Resolution:
    """Resolve the host ports of ``profiles`` the way ``just dev`` does.

    Each variable starts at its environment, ``.env`` or Compose default
    value and moves to the next free port when another process holds it.
    Raises ``FileNotFoundError`` without ``docker-compose.yml`` and
    ``ValueError`` when a configured port is not a number.
    """
    compose_text = (root / COMPOSE_FILE).read_text()
    variables = parse_compose(compose_text, profiles)
    dotenv = load_env(root / ENV_FILE)
    values: dict[str, int] = {}
    for var in variables:
        raw = setting(var.name, dotenv, str(var.default))
        if not raw.isdigit():
            raise ValueError(f"{var.name}={raw} is not a port number.")
        values[var.name] = int(raw)
    address = setting("DEV_BIND_ADDRESS", dotenv, DEFAULT_BIND_ADDRESS)
    own = project_ports(project_name(root, compose_text, dotenv))
    return Resolution(address, own, check_ports(variables, values, address, own))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find free host ports for the dev Compose stack."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="print a report; exit 1 when a port is busy",
    )
    mode.add_argument(
        "--env",
        action="store_true",
        help="print only VAR=port for each busy port",
    )
    mode.add_argument(
        "--port",
        metavar="VAR",
        help="print the port `just dev` uses for VAR (for example DJANGO_PORT)",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Compose profile to check (repeatable; default: dev)",
    )
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="project root (default: .)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""
    args = _parser().parse_args(argv)
    root: Path = args.root
    compose_path = root / COMPOSE_FILE
    if not compose_path.is_file():
        print(f"{compose_path} does not exist.", file=sys.stderr)
        return 2
    try:
        address, _, results = resolve_ports(root, set(args.profile or ["dev"]))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    if args.port:
        for result in results:
            if result.var.name == args.port:
                print(result.free_port)
                return 0
        print(f"{args.port} is not a published port variable.", file=sys.stderr)
        return 2
    busy = [result for result in results if result.busy]
    if args.env:
        for result in busy:
            print(f"{result.var.name}={result.free_port}")
        return 0
    for result in results:
        state = f"busy, next free {result.free_port}" if result.busy else "free"
        print(
            f"{result.var.name}={result.port} ({result.var.service}) "
            f"on {address}: {state}"
        )
    if not busy:
        return 0
    print("Suggested exports:")
    for result in busy:
        print(f"export {result.var.name}={result.free_port}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

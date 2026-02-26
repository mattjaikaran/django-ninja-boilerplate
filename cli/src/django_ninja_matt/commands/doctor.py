"""Doctor command - validate development environment."""

import shutil
import socket
import subprocess
import sys
from pathlib import Path

from rich.table import Table

from django_ninja_matt.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from django_ninja_matt.utils.docker import (
    docker_available,
    docker_compose_available,
    get_compose_version,
    get_docker_version,
)

# Minimum required Python version for this boilerplate.
_MIN_PYTHON_MINOR = 13


def check_python_version() -> tuple[bool, str]:
    """Check that the running Python version meets the minimum requirement (3.13+).

    Returns:
        A tuple of (passed, message) where passed is True when the version
        satisfies the requirement and message is a human-readable description.
    """
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major >= 3 and version.minor >= _MIN_PYTHON_MINOR:
        return True, f"Python {version_str}"
    return (
        False,
        f"Python {version_str} (>= 3.{_MIN_PYTHON_MINOR} required by this boilerplate)",
    )


def check_uv() -> tuple[bool, str]:
    """Check if UV package manager is available."""
    if shutil.which("uv"):
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError:
            return True, "UV available"
    return False, "UV not installed (optional)"


def check_make() -> tuple[bool, str]:
    """Check if Make is available."""
    if shutil.which("make"):
        return True, "Make available"
    return False, "Make not installed (optional)"


def check_git() -> tuple[bool, str]:
    """Check if Git is available."""
    if shutil.which("git"):
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError:
            return True, "Git available"
    return False, "Git not installed"


def check_port(port: int) -> tuple[bool, str]:
    """Check if a local TCP port is available (i.e. nothing is bound to it).

    Args:
        port: The TCP port number to test.

    Returns:
        A tuple of (available, message). available is True when the port is
        free, False when it is already in use.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True, f"Port {port} available"
    except OSError:
        return False, f"Port {port} in use"


def check_service_reachable(host: str, port: int, label: str) -> tuple[bool, str]:
    """Attempt a TCP connection to a service to confirm it is reachable.

    Unlike check_port (which checks that a port is *free*), this function
    checks that a service is *already listening* on the given address.

    Args:
        host: Hostname or IP address to connect to.
        port: TCP port to connect to.
        label: Human-readable service name used in the result message.

    Returns:
        A tuple of (reachable, message). reachable is True when the connection
        succeeds within the 1-second timeout.
    """
    try:
        with socket.create_connection((host, port), timeout=1):
            return True, f"{label} reachable at {host}:{port}"
    except (OSError, TimeoutError):
        return (
            False,
            f"{label} not reachable at {host}:{port} (optional — start the service)",
        )


def check_env_file() -> tuple[bool, str]:
    """Check if .env file exists."""
    if Path(".env").exists():
        return True, ".env file exists"
    if Path(".env.example").exists():
        return False, ".env missing (run: cp .env.example .env)"
    return False, ".env file not found"


def check_docker_compose_file() -> tuple[bool, str]:
    """Check if docker-compose.yml exists."""
    if Path("docker-compose.yml").exists():
        return True, "docker-compose.yml exists"
    return False, "docker-compose.yml not found"


def run_doctor() -> None:
    """Run environment validation checks and print a detailed report.

    Checks system tools, service connectivity, port availability, and project
    configuration files.  Exits with code 1 if any *required* check fails.
    """
    print_header("Django Ninja Boilerplate - Doctor")
    console.print()

    passed = 0
    warned = 0
    failed = 0

    # ------------------------------------------------------------------
    # System Requirements
    # ------------------------------------------------------------------
    console.print("[bold]System Requirements[/bold]")
    console.print("-" * 40)

    # Required checks: Python 3.13+, Docker, Docker Compose, Git
    # Optional checks: uv, make (flagged as warnings)
    required_system_checks = [
        ("Python", check_python_version()),
        ("Docker", (docker_available(), get_docker_version() or "Docker not running")),
        (
            "Docker Compose",
            (docker_compose_available(), get_compose_version() or "Not available"),
        ),
        ("Git", check_git()),
    ]
    optional_system_checks = [
        ("uv", check_uv()),
        ("Make", check_make()),
    ]

    for label, (success, message) in required_system_checks:
        if success:
            print_success(f"{label}: {message}")
            passed += 1
        else:
            print_error(f"{label}: {message}")
            failed += 1

    for label, (success, message) in optional_system_checks:
        if success:
            print_success(f"{label}: {message}")
            passed += 1
        else:
            # uv and make are optional — report as warnings, not failures
            print_warning(f"{label}: {message}")
            warned += 1

    console.print()

    # ------------------------------------------------------------------
    # Service Connectivity
    # Checks whether PostgreSQL and Redis are currently reachable on
    # localhost.  These are warnings (not hard failures) because the
    # services may simply not be started yet.
    # ------------------------------------------------------------------
    console.print("[bold]Service Connectivity[/bold]")
    console.print("-" * 40)

    service_checks = [
        check_service_reachable("127.0.0.1", 5432, "PostgreSQL"),
        check_service_reachable("127.0.0.1", 6379, "Redis"),
    ]

    for success, message in service_checks:
        if success:
            print_success(message)
            passed += 1
        else:
            print_warning(message)
            warned += 1

    console.print()

    # ------------------------------------------------------------------
    # Port Availability (for services we are about to start)
    # ------------------------------------------------------------------
    console.print("[bold]Port Availability[/bold]")
    console.print("-" * 40)

    ports = [
        (8000, "Django"),
        (5555, "Flower"),
    ]

    for port, service in ports:
        success, message = check_port(port)
        if success:
            print_success(f"{service}: {message}")
            passed += 1
        else:
            print_warning(f"{service}: {message}")
            warned += 1

    console.print()

    # ------------------------------------------------------------------
    # Project Configuration
    # ------------------------------------------------------------------
    console.print("[bold]Project Configuration[/bold]")
    console.print("-" * 40)

    config_checks = [
        (".env", check_env_file()),
        ("docker-compose.yml", check_docker_compose_file()),
    ]

    for label, (success, message) in config_checks:
        if success:
            print_success(f"{label}: {message}")
            passed += 1
        else:
            print_error(f"{label}: {message}")
            failed += 1

    console.print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    table = Table(title="Summary", show_header=False)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("[green]Passed[/green]", str(passed))
    table.add_row("[yellow]Warnings[/yellow]", str(warned))
    table.add_row("[red]Failed[/red]", str(failed))

    console.print(table)
    console.print()

    if failed == 0:
        if warned == 0:
            print_success("All checks passed! Your environment is ready.")
        else:
            print_info("Environment is mostly ready with some warnings.")
    else:
        print_error("Some checks failed. Please fix the issues above.")
        raise SystemExit(1)

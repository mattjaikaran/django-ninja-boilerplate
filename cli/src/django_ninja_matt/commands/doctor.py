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


def check_python_version() -> tuple[bool, str]:
    """Check Python version meets requirements."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major >= 3 and version.minor >= 11:
        return True, f"Python {version_str}"
    return False, f"Python {version_str} (>= 3.11 required)"


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
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True, f"Port {port} available"
    except OSError:
        return False, f"Port {port} in use"


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
    """Run environment validation checks."""
    print_header("Django Ninja Boilerplate - Doctor")
    console.print()

    passed = 0
    warned = 0
    failed = 0

    # System Requirements
    console.print("[bold]System Requirements[/bold]")
    console.print("-" * 40)

    checks = [
        ("Python", check_python_version()),
        ("Docker", (docker_available(), get_docker_version() or "Docker not running")),
        (
            "Docker Compose",
            (docker_compose_available(), get_compose_version() or "Not available"),
        ),
        ("UV", check_uv()),
        ("Make", check_make()),
        ("Git", check_git()),
    ]

    for name, (success, message) in checks:
        if success:
            print_success(f"{name}: {message}")
            passed += 1
        elif "optional" in message.lower():
            print_warning(f"{name}: {message}")
            warned += 1
        else:
            print_error(f"{name}: {message}")
            failed += 1

    console.print()

    # Port Availability
    console.print("[bold]Port Availability[/bold]")
    console.print("-" * 40)

    ports = [
        (5432, "PostgreSQL"),
        (6379, "Redis"),
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

    # Project Configuration
    console.print("[bold]Project Configuration[/bold]")
    console.print("-" * 40)

    config_checks = [
        (".env", check_env_file()),
        ("docker-compose.yml", check_docker_compose_file()),
    ]

    for name, (success, message) in config_checks:
        if success:
            print_success(f"{name}: {message}")
            passed += 1
        else:
            print_error(f"{name}: {message}")
            failed += 1

    console.print()

    # Summary
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

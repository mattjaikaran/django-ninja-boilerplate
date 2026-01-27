"""Docker utilities for container operations."""

import shutil
import subprocess


def docker_available() -> bool:
    """Check if Docker is available and running."""
    if not shutil.which("docker"):
        return False

    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def docker_compose_available() -> bool:
    """Check if Docker Compose is available."""
    # Check for docker-compose command
    if shutil.which("docker-compose"):
        return True

    # Check for docker compose plugin
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_docker_compose_command() -> list[str]:
    """Get the appropriate docker compose command."""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


def get_docker_version() -> str | None:
    """Get Docker version string."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_compose_version() -> str | None:
    """Get Docker Compose version string."""
    try:
        # Try docker-compose first
        result = subprocess.run(
            ["docker-compose", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        # Try docker compose plugin
        result = subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

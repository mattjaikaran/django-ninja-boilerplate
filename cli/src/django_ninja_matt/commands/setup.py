"""Setup command - bootstrap development environment."""

import subprocess
from pathlib import Path

from django_ninja_matt.utils.console import (
    print_error,
    print_header,
    print_info,
)


def run_setup(
    auto: bool = False,
    skip_docker: bool = False,
    skip_seed: bool = False,
) -> None:
    """Run the project setup script.

    Args:
        auto: Run in auto mode (no prompts)
        skip_docker: Skip Docker build and start
        skip_seed: Skip seeding sample data
    """
    print_header("Django Ninja Boilerplate - Setup")

    # Check if setup script exists
    setup_script = Path("scripts/setup.sh")
    if not setup_script.exists():
        print_error("Setup script not found: scripts/setup.sh")
        print_info("Make sure you're in the project root directory")
        raise SystemExit(1)

    # Build command
    cmd = ["bash", str(setup_script)]
    if auto:
        cmd.append("--auto")
    if skip_docker:
        cmd.append("--skip-docker")
    if skip_seed:
        cmd.append("--skip-seed")

    # Run setup script
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Setup failed with exit code {e.returncode}")
        raise SystemExit(e.returncode)
    except KeyboardInterrupt:
        print_info("Setup cancelled")
        raise SystemExit(130)

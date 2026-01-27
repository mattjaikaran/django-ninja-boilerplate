"""Git utilities for repository operations."""

import shutil
import subprocess
from pathlib import Path

from django_ninja_matt.utils.console import print_error, print_info, print_success


def git_available() -> bool:
    """Check if git is available."""
    return shutil.which("git") is not None


def clone_repo(
    url: str,
    destination: Path,
    branch: str = "main",
    depth: int = 1,
) -> bool:
    """Clone a git repository.

    Args:
        url: Repository URL
        destination: Local path for the clone
        branch: Branch to clone
        depth: Clone depth (1 for shallow clone)

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = [
            "git",
            "clone",
            "--branch",
            branch,
            "--depth",
            str(depth),
            url,
            str(destination),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print_success(f"Cloned {url}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to clone {url}: {e.stderr}")
        return False


def init_repo(path: Path) -> bool:
    """Initialize a new git repository.

    Args:
        path: Directory to initialize

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["git", "init"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        print_success("Initialized git repository")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to initialize git: {e.stderr}")
        return False


def add_remote(path: Path, name: str, url: str) -> bool:
    """Add a git remote.

    Args:
        path: Repository path
        name: Remote name (e.g., "origin")
        url: Remote URL

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["git", "remote", "add", name, url],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        print_info(f"Added remote {name}: {url}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to add remote: {e.stderr}")
        return False


def create_initial_commit(path: Path, message: str = "Initial commit") -> bool:
    """Create an initial commit.

    Args:
        path: Repository path
        message: Commit message

    Returns:
        True if successful, False otherwise
    """
    try:
        # Stage all files
        subprocess.run(
            ["git", "add", "."],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )

        # Create commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )

        print_success("Created initial commit")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create commit: {e.stderr}")
        return False


def remove_git_history(path: Path) -> bool:
    """Remove .git directory to clear history.

    Args:
        path: Repository path

    Returns:
        True if successful, False otherwise
    """
    git_dir = path / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)
        return True
    return False

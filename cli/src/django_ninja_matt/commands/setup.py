"""Configure and bootstrap the local development environment."""

from __future__ import annotations

import os
import subprocess
from enum import StrEnum
from pathlib import Path

import questionary

from django_ninja_matt.utils.console import (
    print_error,
    print_header,
    print_info,
    print_success,
)

DEFAULT_TASK_BACKEND = "celery"


class TaskBackend(StrEnum):
    """Supported asynchronous task backends."""

    CELERY = "celery"
    HUEY = "huey"
    DJANGO_Q = "django_q"
    DJANGO_RQ = "django_rq"
    DRAMATIQ = "dramatiq"


def prompt_task_backend() -> TaskBackend:
    """Ask which task worker the development stack must start."""
    choices = [
        questionary.Choice("Celery (default)", value=TaskBackend.CELERY),
        questionary.Choice("Huey", value=TaskBackend.HUEY),
        questionary.Choice("django-q2", value=TaskBackend.DJANGO_Q),
        questionary.Choice("django-rq", value=TaskBackend.DJANGO_RQ),
        questionary.Choice("Dramatiq", value=TaskBackend.DRAMATIQ),
    ]
    result = questionary.select(
        "Choose a task backend:",
        choices=choices,
        default=TaskBackend.CELERY,
    ).ask()
    return TaskBackend(result or DEFAULT_TASK_BACKEND)


def configure_environment(
    project_root: Path,
    backend: TaskBackend,
) -> Path:
    """Create or update the project environment file."""
    example_path = project_root / ".env.example"
    env_path = project_root / ".env"
    if not example_path.exists():
        raise FileNotFoundError(f"Environment template not found: {example_path}")

    source = env_path if env_path.exists() else example_path
    lines = source.read_text().splitlines()
    setting = f"TASK_BACKEND={backend.value}"
    for index, line in enumerate(lines):
        if line.startswith("TASK_BACKEND="):
            lines[index] = setting
            break
    else:
        lines.append(setting)

    env_path.write_text("\n".join(lines) + "\n")
    return env_path


def read_environment_value(env_path: Path, key: str, default: str) -> str:
    """Read a value using the same process-over-file precedence as Compose."""
    if key in os.environ:
        return os.environ[key] or default
    if not env_path.exists():
        return default

    for line in env_path.read_text().splitlines():
        setting, separator, value = line.partition("=")
        if separator and setting.strip() == key:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            return value or default
    return default


def run_setup(
    auto: bool = False,
    backend: TaskBackend | None = None,
) -> None:
    """Configure the task backend and run the one-command bootstrap."""
    print_header("Django Ninja Boilerplate - Setup")
    project_root = Path.cwd()
    if not (project_root / "justfile").exists():
        print_error("Run this command from the project root directory.")
        raise SystemExit(1)

    selected_backend = backend or (
        TaskBackend.CELERY if auto else prompt_task_backend()
    )
    try:
        env_path = configure_environment(project_root, selected_backend)
    except (FileNotFoundError, OSError) as exc:
        print_error(str(exc))
        raise SystemExit(1) from exc

    print_info(f"Configured {env_path.name}: TASK_BACKEND={selected_backend.value}")
    print_info("Building the selected stack and preparing the database.")
    try:
        subprocess.run(["just", "setup-services"], check=True)
    except FileNotFoundError as exc:
        print_error("The 'just' command is required. Install it and run setup again.")
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print_error(f"Setup failed with exit code {exc.returncode}.")
        raise SystemExit(exc.returncode) from exc
    except KeyboardInterrupt as exc:
        print_info("Setup cancelled.")
        raise SystemExit(130) from exc

    print_success("Setup complete.")
    port = read_environment_value(env_path, "DJANGO_PORT", "8000")
    print_info(f"Sign in at http://localhost:{port}/admin/ with the .env superuser.")


__all__ = [
    "DEFAULT_TASK_BACKEND",
    "TaskBackend",
    "configure_environment",
    "read_environment_value",
    "prompt_task_backend",
    "run_setup",
]

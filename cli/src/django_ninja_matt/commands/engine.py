"""Scaffold an engine with the project's generate_feature command."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from django_ninja_matt.utils.console import print_error, print_step, print_success
from django_ninja_matt.utils.project_root import find_project_root


def build_add_engine_command(name: str, modules: str | None) -> list[str]:
    """Build the manage.py argv that scaffolds engine ``name`` and its modules."""
    python = ["uv", "run", "python"] if shutil.which("uv") else [sys.executable]
    command = [*python, "manage.py", "generate_feature", "engine", "--app-name", name]
    if modules:
        command += ["--modules", modules]
    return command


def add_engine(
    name: Annotated[
        str,
        typer.Argument(
            help=(
                "Name of the engine (e.g. 'booking'). The engine lives in "
                "engines/NAME/ and its routes start with /api/NAME/."
            )
        ),
    ],
    modules: Annotated[
        str | None,
        typer.Option(
            "--modules",
            "-m",
            help=(
                "Comma-separated module names (e.g. 'artists,tours'). Each module "
                "is a Django app with its own API. Defaults to one module named "
                "after the engine."
            ),
        ),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help=(
                "Directory inside the project. The CLI walks up from here to the "
                "directory that holds manage.py. Defaults to the current directory."
            ),
        ),
    ] = None,
) -> None:
    """Scaffold an engine: a bounded context that groups several module APIs.

    Runs [bold]manage.py generate_feature engine --app-name NAME --modules
    LIST[/bold] from the project root. Each module gets models, repositories,
    DTOs, services, schemas and a controller, and is added to INSTALLED_APPS
    and api/urls.py with its migration. See docs/ARCHITECTURE.md, section
    "Engines".

    Examples:

        dnm add-engine booking --modules artists,tours,agents
    """
    root = find_project_root(path or Path.cwd())
    if root is None:
        print_error(
            f"No manage.py found in '{(path or Path.cwd()).resolve()}' or any parent "
            "directory. Run add-engine inside a django-ninja-boilerplate project."
        )
        raise typer.Exit(1)

    if (root / "engines" / name).exists():
        print_error(f"Directory '{root / 'engines' / name}' already exists")
        raise typer.Exit(1)

    command = build_add_engine_command(name, modules)
    print_step(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode != 0:
        print_error(f"Generator failed with exit code {result.returncode}")
        raise typer.Exit(result.returncode)

    print_success(f"Engine '{name}' scaffolded at {root / 'engines' / name}")

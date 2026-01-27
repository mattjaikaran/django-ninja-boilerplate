"""Main CLI application using Typer."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from django_ninja_matt import __version__
from django_ninja_matt.commands.doctor import run_doctor
from django_ninja_matt.commands.init import run_init
from django_ninja_matt.commands.setup import run_setup
from django_ninja_matt.config import DeploymentTarget, ProjectType

# Create Typer app
app = typer.Typer(
    name="django-ninja-matt",
    help="CLI tool for scaffolding Django Ninja Stack projects",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"django-ninja-matt version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Django Ninja Matt - Modern Django API scaffolding."""
    pass


@app.command()
def init(
    name: Annotated[
        str,
        typer.Argument(help="Project name (will be created as directory)"),
    ],
    path: Annotated[
        Optional[Path],
        typer.Option(
            "--path",
            "-p",
            help="Parent directory for the project",
        ),
    ] = None,
    project_type: Annotated[
        Optional[ProjectType],
        typer.Option(
            "--type",
            "-t",
            help="Project type",
            case_sensitive=False,
        ),
    ] = None,
    deployment: Annotated[
        Optional[DeploymentTarget],
        typer.Option(
            "--deployment",
            "-d",
            help="Deployment target",
            case_sensitive=False,
        ),
    ] = None,
    no_celery: Annotated[
        bool,
        typer.Option(
            "--no-celery",
            help="Skip Celery setup",
        ),
    ] = False,
    no_redis: Annotated[
        bool,
        typer.Option(
            "--no-redis",
            help="Skip Redis setup",
        ),
    ] = False,
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git",
            help="Skip Git initialization",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompts",
        ),
    ] = False,
) -> None:
    """Create a new Django Ninja Stack project.

    Examples:
        django-ninja-matt init my-app
        dnm init my-app --type standalone
        dnm init my-app --type monorepo --deployment railway
    """
    run_init(
        name=name,
        path=path or Path.cwd(),
        project_type=project_type,
        deployment=deployment,
        use_celery=not no_celery,
        use_redis=not no_redis,
        init_git=not no_git,
        skip_prompts=yes,
    )


@app.command()
def doctor() -> None:
    """Validate your development environment.

    Checks for required tools (Python, Docker, etc.), port availability,
    and project configuration.
    """
    run_doctor()


@app.command()
def setup(
    auto: Annotated[
        bool,
        typer.Option(
            "--auto",
            "-a",
            help="Run in auto mode (no prompts)",
        ),
    ] = False,
    skip_docker: Annotated[
        bool,
        typer.Option(
            "--skip-docker",
            help="Skip Docker build and start",
        ),
    ] = False,
    skip_seed: Annotated[
        bool,
        typer.Option(
            "--skip-seed",
            help="Skip seeding sample data",
        ),
    ] = False,
) -> None:
    """Bootstrap the development environment.

    Runs the project setup script to build Docker images, run migrations,
    and seed initial data.
    """
    run_setup(auto=auto, skip_docker=skip_docker, skip_seed=skip_seed)


# Allow running without subcommand for quick project creation
@app.command(name="create", hidden=True)
def create_alias(
    name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """Alias for init command."""
    run_init(name=name, path=Path.cwd())


def show_welcome() -> None:
    """Show welcome banner."""
    text = Text()
    text.append("Django Ninja Matt", style="bold cyan")
    text.append("\n")
    text.append("Modern Django API scaffolding with best practices", style="dim")

    panel = Panel(
        text,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


if __name__ == "__main__":
    app()

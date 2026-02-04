"""Main CLI application using Typer."""

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from django_ninja_matt import __version__
from django_ninja_matt.commands.doctor import run_doctor
from django_ninja_matt.commands.init import run_init
from django_ninja_matt.commands.setup import run_setup
from django_ninja_matt.config import DeploymentTarget, ProjectType
from django_ninja_matt.utils.console import (
    print_error,
    print_info,
    print_step,
    print_success,
)

# Create Typer app
app = typer.Typer(
    name="django-ninja-matt",
    help="CLI tool for scaffolding Django Ninja Boilerplate projects",
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
        bool | None,
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
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Parent directory for the project",
        ),
    ] = None,
    project_type: Annotated[
        ProjectType | None,
        typer.Option(
            "--type",
            "-t",
            help="Project type",
            case_sensitive=False,
        ),
    ] = None,
    deployment: Annotated[
        DeploymentTarget | None,
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
    """Create a new Django Ninja Boilerplate project.

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


@app.command()
def test(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Run tests in verbose mode",
        ),
    ] = False,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            "-c",
            help="Run tests with coverage report",
        ),
    ] = False,
    path: Annotated[
        str | None,
        typer.Argument(help="Specific test path or file to run"),
    ] = None,
) -> None:
    """Run pytest with common options.

    Examples:
        dnm test
        dnm test -v
        dnm test --coverage
        dnm test apps/users/tests.py
    """
    print_step("Running tests...")

    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])

    if path:
        cmd.append(path)

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print_success("All tests passed!")
        else:
            print_error(f"Tests failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print_error("pytest not found. Make sure it's installed: pip install pytest")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Tests cancelled")
        raise typer.Exit(130)


@app.command()
def lint(
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            "-f",
            help="Automatically fix issues where possible",
        ),
    ] = False,
    check_only: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check, don't format (useful for CI)",
        ),
    ] = False,
) -> None:
    """Run ruff check and format.

    Examples:
        dnm lint
        dnm lint --fix
        dnm lint --check
    """
    print_step("Running linter...")

    # Run ruff check
    check_cmd = ["ruff", "check", "."]
    if fix:
        check_cmd.append("--fix")

    try:
        result = subprocess.run(check_cmd, check=False)
        check_passed = result.returncode == 0

        # Run ruff format
        if not check_only:
            print_step("Running formatter...")
            format_cmd = ["ruff", "format", "."]
            if check_only:
                format_cmd.append("--check")
            format_result = subprocess.run(format_cmd, check=False)
            format_passed = format_result.returncode == 0
        else:
            print_step("Checking format...")
            format_cmd = ["ruff", "format", ".", "--check"]
            format_result = subprocess.run(format_cmd, check=False)
            format_passed = format_result.returncode == 0

        if check_passed and format_passed:
            print_success("Linting and formatting passed!")
        else:
            print_error("Linting or formatting issues found")
            raise typer.Exit(1)

    except FileNotFoundError:
        print_error("ruff not found. Make sure it's installed: pip install ruff")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Linting cancelled")
        raise typer.Exit(130)


@app.command()
def migrate(
    app_label: Annotated[
        str | None,
        typer.Argument(help="App label to migrate (optional)"),
    ] = None,
    make: Annotated[
        bool,
        typer.Option(
            "--make",
            "-m",
            help="Create new migrations (makemigrations)",
        ),
    ] = False,
) -> None:
    """Run Django migrations.

    Examples:
        dnm migrate
        dnm migrate --make
        dnm migrate users
        dnm migrate users --make
    """
    if make:
        print_step("Creating migrations...")
        cmd = ["python", "manage.py", "makemigrations"]
        if app_label:
            cmd.append(app_label)

        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print_error("Failed to create migrations")
                raise typer.Exit(result.returncode)
            print_success("Migrations created!")
        except FileNotFoundError:
            print_error("manage.py not found. Make sure you're in the project root")
            raise typer.Exit(1)

    print_step("Running migrations...")
    cmd = ["python", "manage.py", "migrate"]
    if app_label:
        cmd.append(app_label)

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print_success("Migrations applied successfully!")
        else:
            print_error(f"Migration failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print_error("manage.py not found. Make sure you're in the project root")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Migration cancelled")
        raise typer.Exit(130)


@app.command()
def shell(
    plus: Annotated[
        bool,
        typer.Option(
            "--plus",
            "-p",
            help="Use shell_plus (requires django-extensions)",
        ),
    ] = False,
) -> None:
    """Open Django shell.

    Examples:
        dnm shell
        dnm shell --plus
    """
    if plus:
        print_step("Opening Django shell_plus...")
        cmd = ["python", "manage.py", "shell_plus"]
    else:
        print_step("Opening Django shell...")
        cmd = ["python", "manage.py", "shell"]

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print_error(f"Shell exited with code {result.returncode}")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print_error("manage.py not found. Make sure you're in the project root")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Shell closed")
        raise typer.Exit(0)


@app.command()
def logs(
    service: Annotated[
        str | None,
        typer.Argument(help="Service name to view logs for (e.g., web, db, redis)"),
    ] = None,
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            "-f",
            help="Follow log output",
        ),
    ] = False,
    tail: Annotated[
        int,
        typer.Option(
            "--tail",
            "-n",
            help="Number of lines to show from the end",
        ),
    ] = 100,
) -> None:
    """View Docker logs.

    Examples:
        dnm logs
        dnm logs web
        dnm logs web -f
        dnm logs --tail 50
    """
    print_step("Fetching Docker logs...")

    cmd = ["docker", "compose", "logs"]

    if follow:
        cmd.append("-f")

    cmd.extend(["--tail", str(tail)])

    if service:
        cmd.append(service)

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print_error(f"Failed to fetch logs (exit code {result.returncode})")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print_error("docker not found. Make sure Docker is installed and running")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Log streaming stopped")
        raise typer.Exit(0)


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

# file-length-max: 1100
"""Main CLI application using Typer."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from django_ninja_matt import __version__
from django_ninja_matt.commands.doctor import run_doctor
from django_ninja_matt.commands.init import run_init
from django_ninja_matt.commands.setup import TaskBackend, run_setup
from django_ninja_matt.config import DeploymentTarget, EmailBackend, ProjectType
from django_ninja_matt.utils.console import (
    print_error,
    print_info,
    print_step,
    print_success,
)

# Create Typer app
app = typer.Typer(
    name="django-ninja-matt",
    help=(
        "Scaffold and manage Django Ninja Boilerplate projects. "
        "Run [bold]dnm init <name>[/bold] to create a new project, "
        "or [bold]dnm --help[/bold] on any sub-command for details."
    ),
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold]django-ninja-matt[/bold]", f"v{__version__}")
        table.add_row(
            "[dim]Python[/dim]",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
        try:
            import django

            table.add_row("[dim]Django[/dim]", django.get_version())
        except ImportError:
            pass
        console.print(table)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help=(
                "Print the current version of django-ninja-matt together with the "
                "active Python and Django versions, then exit."
            ),
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Django Ninja Matt — scaffold and manage Django Ninja Boilerplate projects.

    Run [bold]dnm init <project-name>[/bold] to create a new project, or pass
    [bold]--help[/bold] to any sub-command for detailed usage information.
    """
    pass


@app.command()
def init(
    name: Annotated[
        str,
        typer.Argument(
            help=(
                "Name of the new project. Used as the directory name and Python "
                "package identifier (spaces and underscores are normalised to hyphens)."
            )
        ),
    ],
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help=(
                "Parent directory in which to create the project folder. "
                "Defaults to the current working directory."
            ),
        ),
    ] = None,
    project_type: Annotated[
        ProjectType | None,
        typer.Option(
            "--type",
            "-t",
            help=(
                "Project layout to generate. "
                "'standalone' creates a Django API only; "
                "'monorepo' adds a React Vite frontend alongside the backend."
            ),
            case_sensitive=False,
        ),
    ] = None,
    deployment: Annotated[
        DeploymentTarget | None,
        typer.Option(
            "--deployment",
            "-d",
            help=(
                "Primary deployment target. Generates the matching configuration "
                "files (e.g. railway.toml, render.yaml, Helm charts). "
                "Choices: docker (default), railway, render, kubernetes."
            ),
            case_sensitive=False,
        ),
    ] = None,
    no_celery: Annotated[
        bool,
        typer.Option(
            "--no-celery",
            help=(
                "Omit Celery and django-celery-beat from the generated project. "
                "Useful for lightweight APIs that do not require background tasks."
            ),
        ),
    ] = False,
    no_redis: Annotated[
        bool,
        typer.Option(
            "--no-redis",
            help=(
                "Omit Redis from the generated project. "
                "Ignored when Celery is included (Redis is required as the broker)."
            ),
        ),
    ] = False,
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git",
            help=(
                "Skip initialising a git repository inside the new project. "
                "Useful when you plan to add the project to an existing repo."
            ),
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help=(
                "Accept all defaults and skip interactive confirmation prompts. "
                "Suitable for scripted or CI environments."
            ),
        ),
    ] = False,
    docstrings: Annotated[
        bool,
        typer.Option(
            "--docstrings",
            help=(
                "Generate Google-style docstrings on all public classes and methods "
                "in controllers, service classes, and schema classes. "
                "Off by default; opt in when you want self-documenting generated code."
            ),
        ),
    ] = False,
    email_backend: Annotated[
        EmailBackend,
        typer.Option(
            "--email-backend",
            help=(
                "Email delivery backend to configure in the generated .env. "
                "'console' (default) logs emails to stdout for local development; "
                "'resend' uses the Resend API via django-anymail; "
                "'smtp' configures a standard SMTP server."
            ),
            case_sensitive=False,
        ),
    ] = EmailBackend.CONSOLE,
) -> None:
    """Create a new Django Ninja Boilerplate project.

    Clones the boilerplate repository, customises it with your project name and
    selected options, then optionally initialises a fresh git repository.

    Examples:

        dnm init my-api

        dnm init my-api --type standalone --deployment railway

        dnm init my-api --type monorepo --no-celery --yes

        dnm init my-api --docstrings --email-backend resend
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
        include_docstrings=docstrings,
        email_backend=email_backend,
    )


@app.command()
def doctor() -> None:
    """Validate your development environment before starting a project.

    Runs a suite of checks and reports pass / warn / fail for each:

    \b
    System tools : Python 3.13+, uv, Docker, Docker Compose, Make, Git
    Services     : PostgreSQL (port 5432), Redis (port 6379)
    Ports        : Django (8000), Celery Flower (5555)
    Project files: .env, docker-compose.yml

    Exit code is 0 when all required checks pass, 1 if any required check fails.

    Examples:

        dnm doctor
    """
    run_doctor()


@app.command()
def setup(
    auto: Annotated[
        bool,
        typer.Option(
            "--auto",
            "-a",
            help="Use the default task backend without prompting.",
        ),
    ] = False,
    backend: Annotated[
        TaskBackend | None,
        typer.Option(
            "--backend",
            help="Task backend to configure before the stack starts.",
            case_sensitive=False,
        ),
    ] = None,
) -> None:
    """Configure and bootstrap the local development environment."""
    run_setup(auto=auto, backend=backend)


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
            help="Pass -v to pytest for per-test result lines instead of dots.",
        ),
    ] = False,
    coverage: Annotated[
        bool,
        typer.Option(
            "--coverage",
            "-c",
            help=(
                "Collect coverage data and print a term-missing report. "
                "Equivalent to: pytest --cov=. --cov-report=term-missing"
            ),
        ),
    ] = False,
    path: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional path to a specific test file, directory, or "
                "pytest node ID (e.g. core/tests/test_auth.py::TestLogin)."
            )
        ),
    ] = None,
) -> None:
    """Run the test suite with pytest.

    Uses [bold]api.settings.test[/bold] as the Django settings module so that
    SQLite is used locally and no real services are required.

    Examples:

        dnm test

        dnm test -v

        dnm test --coverage

        dnm test core/tests/test_auth.py
    """
    print_step("Running tests...")

    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])

    if path:
        cmd.append(path)

    # Ensure test settings are used
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "api.settings.test"}

    try:
        # Argument list, no shell; the operator runs this local dev CLI.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        result = subprocess.run(cmd, check=False, env=env)
        if result.returncode == 0:
            print_success("All tests passed!")
        else:
            print_error(f"Tests failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print_error("pytest not found. Make sure it's installed: uv add --dev pytest")
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
            help=(
                "Pass --fix to ruff so that auto-fixable lint violations are "
                "corrected in-place before reporting remaining issues."
            ),
        ),
    ] = False,
    check_only: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Run ruff format in check-only mode (exits non-zero if any file "
                "would be reformatted). No files are modified. Useful in CI."
            ),
        ),
    ] = False,
) -> None:
    """Lint and format the codebase with ruff.

    Runs [bold]ruff check[/bold] followed by [bold]ruff format[/bold]. Both tools
    must be installed (they are listed under [dev] extras in pyproject.toml).

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
        # Argument list, no shell; the operator runs this local dev CLI.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        result = subprocess.run(check_cmd, check=False)
        check_passed = result.returncode == 0

        # Run ruff format
        if not check_only:
            print_step("Running formatter...")
            format_cmd = ["ruff", "format", "."]
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
            format_result = subprocess.run(format_cmd, check=False)
            format_passed = format_result.returncode == 0
        else:
            print_step("Checking format...")
            format_cmd = ["ruff", "format", ".", "--check"]
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
            format_result = subprocess.run(format_cmd, check=False)
            format_passed = format_result.returncode == 0

        if check_passed and format_passed:
            print_success("Linting and formatting passed!")
        else:
            print_error("Linting or formatting issues found")
            raise typer.Exit(1)

    except FileNotFoundError:
        print_error("ruff not found. Make sure it's installed: uv add --dev ruff")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Linting cancelled")
        raise typer.Exit(130)


@app.command()
def migrate(
    app_label: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional Django app label to scope the migration command. "
                "When omitted all apps are migrated."
            )
        ),
    ] = None,
    make: Annotated[
        bool,
        typer.Option(
            "--make",
            "-m",
            help=(
                "Run 'makemigrations' before applying migrations. "
                "Creates new migration files for any detected model changes."
            ),
        ),
    ] = False,
) -> None:
    """Apply Django database migrations (optionally creating them first).

    Must be run from the project root directory where [bold]manage.py[/bold] lives.

    Examples:

        dnm migrate

        dnm migrate --make

        dnm migrate core

        dnm migrate core --make
    """
    if make:
        print_step("Creating migrations...")
        cmd = ["python", "manage.py", "makemigrations"]
        if app_label:
            cmd.append(app_label)

        try:
            # Argument list, no shell; the operator runs this local dev CLI.
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
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
        # Argument list, no shell; the operator runs this local dev CLI.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
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
            help=(
                "Open shell_plus (from django-extensions) instead of the standard "
                "Django shell. Provides IPython, auto-imported models, and more."
            ),
        ),
    ] = False,
) -> None:
    """Open an interactive Django shell.

    Must be run from the project root directory where [bold]manage.py[/bold] lives.

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
        # Argument list, no shell; the operator runs this local dev CLI.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
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
        typer.Argument(
            help=(
                "Name of a specific Docker Compose service whose logs you want "
                "(e.g. web, db, redis, celery). Omit to see all services."
            )
        ),
    ] = None,
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            "-f",
            help="Stream logs in real time (equivalent to docker compose logs -f).",
        ),
    ] = False,
    tail: Annotated[
        int,
        typer.Option(
            "--tail",
            "-n",
            help="Number of log lines to show from the end of each service's output.",
        ),
    ] = 100,
) -> None:
    """Stream or display Docker Compose service logs.

    Wraps [bold]docker compose logs[/bold]. Docker must be installed and the
    Compose services must be running (or have been run previously).

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
        # Argument list, no shell; the operator runs this local dev CLI.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
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


def find_project_root(start: Path) -> Path | None:
    """Return the nearest directory at or above ``start`` that holds manage.py."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "manage.py").is_file():
            return candidate
    return None


def build_add_app_command(name: str, *, wire: bool) -> list[str]:
    """Build the manage.py argv that scaffolds ``name`` with the project generator."""
    python = ["uv", "run", "python"] if shutil.which("uv") else [sys.executable]
    if wire:
        return [
            *python,
            "manage.py",
            "generate_feature",
            "api_endpoint",
            "--app-name",
            name,
        ]
    return [*python, "manage.py", "startapp_extended", name]


@app.command(name="add-app")
def add_app(
    name: Annotated[
        str,
        typer.Argument(
            help=(
                "Name of the new Django app (e.g. 'products', 'orders'). "
                "Used as the directory name, URL prefix, and Python module name."
            )
        ),
    ],
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
    no_wire: Annotated[
        bool,
        typer.Option(
            "--no-wire",
            help=(
                "Only scaffold the app (manage.py startapp_extended). Do not edit "
                "INSTALLED_APPS or api/urls.py, and do not create the migration."
            ),
        ),
    ] = False,
) -> None:
    """Scaffold a new Django app with the project's own generator.

    By default this runs [bold]manage.py generate_feature api_endpoint
    --app-name NAME[/bold] from the project root. That creates the app, adds it
    to INSTALLED_APPS, registers its controller in api/urls.py, and creates the
    initial migration. With [bold]--no-wire[/bold] it runs
    [bold]manage.py startapp_extended NAME[/bold] instead, which only creates
    the app directory.

    Examples:

        dnm add-app products

        dnm add-app orders --path api/

        dnm add-app products --no-wire
    """
    root = find_project_root(path or Path.cwd())
    if root is None:
        print_error(
            f"No manage.py found in '{(path or Path.cwd()).resolve()}' or any parent "
            "directory. Run add-app inside a django-ninja-boilerplate project."
        )
        raise typer.Exit(1)

    if (root / name).exists():
        print_error(f"Directory '{root / name}' already exists")
        raise typer.Exit(1)

    command = build_add_app_command(name, wire=not no_wire)
    print_step(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode != 0:
        print_error(f"Generator failed with exit code {result.returncode}")
        raise typer.Exit(result.returncode)

    print_success(f"App '{name}' scaffolded at {root / name}")
    if no_wire:
        print_info("Next steps:")
        print_info(f"  1. Add '{name}' to INSTALLED_APPS in api/settings/common.py")
        print_info("  2. Register the controller in api/urls.py")
        print_info("  3. Run: dnm migrate --make")


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

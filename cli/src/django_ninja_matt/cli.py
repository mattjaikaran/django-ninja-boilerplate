# file-length-max: 1100
"""Main CLI application using Typer."""

import os
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
from django_ninja_matt.commands.setup import run_setup
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
            help=(
                "Run in fully automatic mode — no interactive prompts. "
                "All steps use their default values. Suitable for CI pipelines."
            ),
        ),
    ] = False,
    skip_docker: Annotated[
        bool,
        typer.Option(
            "--skip-docker",
            help=(
                "Skip the 'docker compose build' and 'docker compose up' steps. "
                "Use this when Docker services are already running."
            ),
        ),
    ] = False,
    skip_seed: Annotated[
        bool,
        typer.Option(
            "--skip-seed",
            help=(
                "Skip loading sample / seed data into the database after migrations. "
                "Useful for fresh production-like environments."
            ),
        ),
    ] = False,
) -> None:
    """Bootstrap the development environment from scratch.

    Delegates to [bold]scripts/setup.sh[/bold] and runs the following steps
    in order (unless skipped):

    \b
    1. Build Docker images
    2. Start Docker services (db, redis, etc.)
    3. Apply database migrations
    4. Seed initial / sample data

    Must be run from the project root directory where [bold]scripts/setup.sh[/bold]
    is located.

    Examples:

        dnm setup

        dnm setup --auto

        dnm setup --skip-docker --skip-seed
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
        result = subprocess.run(check_cmd, check=False)
        check_passed = result.returncode == 0

        # Run ruff format
        if not check_only:
            print_step("Running formatter...")
            format_cmd = ["ruff", "format", "."]
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
                "Parent directory in which to create the app folder. "
                "Defaults to the current working directory (project root)."
            ),
        ),
    ] = None,
    docstrings: Annotated[
        bool,
        typer.Option(
            "--docstrings",
            help=(
                "Add Google-style docstrings to all generated public classes and "
                "methods (controller actions, service methods, schema classes). "
                "Off by default; opt in for self-documenting generated code."
            ),
        ),
    ] = False,
) -> None:
    """Scaffold a new Django app following the boilerplate conventions.

    Generates the full standard directory structure with stub files for every
    layer, ready to extend:

    \b
    <app>/
    ├── __init__.py
    ├── apps.py
    ├── admin.py
    ├── models/
    │   ├── __init__.py
    │   └── <singular>.py      (BaseModel subclass)
    ├── controllers/
    │   └── __init__.py        (api_controller with CRUD endpoints)
    ├── schemas/
    │   └── __init__.py        (Schema + CreateSchema)
    ├── services/
    │   └── __init__.py
    └── tests/
        ├── __init__.py
        └── test_<singular>.py

    After scaffolding, add the app to INSTALLED_APPS and register the controller
    in [bold]api/urls.py[/bold], then run [bold]dnm migrate --make[/bold].

    Examples:

        dnm add-app products

        dnm add-app orders --path apps/

        dnm add-app products --docstrings
    """
    app_dir = (path or Path.cwd()) / name

    if app_dir.exists():
        print_error(f"Directory '{app_dir}' already exists")
        raise typer.Exit(1)

    print_step(f"Scaffolding app '{name}'...")

    # Create directory structure
    subdirs = ["models", "controllers", "schemas", "services", "tests"]
    for subdir in subdirs:
        (app_dir / subdir).mkdir(parents=True, exist_ok=True)

    # App __init__.py
    (app_dir / "__init__.py").write_text("")

    # models/__init__.py with base model
    model_name = name.rstrip("s").capitalize()
    (app_dir / "models" / "__init__.py").write_text(
        f'"""Models for {name} app."""\n\n'
        f"from .{name.rstrip('s')} import {model_name}  # noqa: F401\n"
    )
    (app_dir / "models" / f"{name.rstrip('s')}.py").write_text(
        f'"""Model for {model_name}."""\n\n'
        "from api.models import BaseModel\n"
        "from django.db import models\n\n\n"
        f"class {model_name}(BaseModel):\n"
        f'    """Represents a {model_name.lower()}."""\n\n'
        "    name = models.CharField(max_length=255)\n"
        '    description = models.TextField(blank=True, default="")\n\n'
        "    class Meta:\n"
        f'        verbose_name = "{model_name}"\n'
        f'        verbose_name_plural = "{model_name}s"\n'
        '        ordering = ["-created_at"]\n\n'
        "    def __str__(self) -> str:\n"
        + (
            '        """Return a human-readable string representation."""\n'
            if docstrings
            else ""
        )
        + "        return self.name\n"
    )

    # Build controller content — optionally with Google-style docstrings
    singular = name.rstrip("s")
    if docstrings:
        controller_content = (
            f'"""API controllers for {name} app."""\n\n'
            "from ninja_extra import api_controller, http_delete, http_get, http_post, http_put\n\n"
            f"from {name}.models import {model_name}\n"
            f"from {name}.schemas import {model_name}Schema, Create{model_name}Schema\n\n\n"
            f'@api_controller("/{name}", tags=["{name.capitalize()}"])\n'
            f"class {model_name}Controller:\n"
            f'    """Controller exposing CRUD endpoints for {model_name} resources."""\n\n'
            f'    @http_get("/", response={{200: list[{model_name}Schema]}})\n'
            f"    def list_{name}(self, request):\n"
            f'        """Return a list of all {name}.\n\n'
            f"        Returns:\n"
            f"            HTTP 200 with a list of {model_name}Schema objects.\n"
            f'        """\n'
            f"        return 200, {model_name}.objects.all()\n\n"
            f'    @http_post("/", response={{201: {model_name}Schema}})\n'
            f"    def create_{singular}(self, request, payload: Create{model_name}Schema):\n"
            f'        """Create a new {model_name}.\n\n'
            f"        Args:\n"
            f"            payload: Validated fields for the new {model_name}.\n\n"
            f"        Returns:\n"
            f"            HTTP 201 with the created {model_name}Schema.\n"
            f'        """\n'
            f"        obj = {model_name}.objects.create(**payload.dict())\n"
            f"        return 201, obj\n\n"
            f'    @http_get("/{{id}}", response={{200: {model_name}Schema}})\n'
            f"    def get_{singular}(self, request, id: str):\n"
            f'        """Retrieve a single {model_name} by ID.\n\n'
            f"        Args:\n"
            f"            id: UUID primary key of the {model_name}.\n\n"
            f"        Returns:\n"
            f"            HTTP 200 with the matching {model_name}Schema.\n"
            f'        """\n'
            f"        return 200, {model_name}.objects.get(id=id)\n\n"
            f'    @http_put("/{{id}}", response={{200: {model_name}Schema}})\n'
            f"    def update_{singular}(self, request, id: str, payload: Create{model_name}Schema):\n"
            f'        """Update an existing {model_name}.\n\n'
            f"        Args:\n"
            f"            id: UUID primary key of the {model_name} to update.\n"
            f"            payload: Updated field values.\n\n"
            f"        Returns:\n"
            f"            HTTP 200 with the updated {model_name}Schema.\n"
            f'        """\n'
            f"        obj = {model_name}.objects.get(id=id)\n"
            f"        for attr, value in payload.dict().items():\n"
            f"            setattr(obj, attr, value)\n"
            f"        obj.save()\n"
            f"        return 200, obj\n\n"
            f'    @http_delete("/{{id}}", response={{204: None}})\n'
            f"    def delete_{singular}(self, request, id: str):\n"
            f'        """Delete a {model_name} by ID.\n\n'
            f"        Args:\n"
            f"            id: UUID primary key of the {model_name} to delete.\n\n"
            f"        Returns:\n"
            f"            HTTP 204 with no content.\n"
            f'        """\n'
            f"        {model_name}.objects.filter(id=id).delete()\n"
            f"        return 204, None\n"
        )
    else:
        controller_content = (
            f'"""API controllers for {name} app."""\n\n'
            "from ninja_extra import api_controller, http_delete, http_get, http_post, http_put\n\n"
            f"from {name}.models import {model_name}\n"
            f"from {name}.schemas import {model_name}Schema, Create{model_name}Schema\n\n\n"
            f'@api_controller("/{name}", tags=["{name.capitalize()}"])\n'
            f"class {model_name}Controller:\n"
            f'    @http_get("/", response={{200: list[{model_name}Schema]}})\n'
            f"    def list_{name}(self, request):\n"
            f"        return 200, {model_name}.objects.all()\n\n"
            f'    @http_post("/", response={{201: {model_name}Schema}})\n'
            f"    def create_{singular}(self, request, payload: Create{model_name}Schema):\n"
            f"        obj = {model_name}.objects.create(**payload.dict())\n"
            f"        return 201, obj\n\n"
            f'    @http_get("/{{id}}", response={{200: {model_name}Schema}})\n'
            f"    def get_{singular}(self, request, id: str):\n"
            f"        return 200, {model_name}.objects.get(id=id)\n\n"
            f'    @http_put("/{{id}}", response={{200: {model_name}Schema}})\n'
            f"    def update_{singular}(self, request, id: str, payload: Create{model_name}Schema):\n"
            f"        obj = {model_name}.objects.get(id=id)\n"
            f"        for attr, value in payload.dict().items():\n"
            f"            setattr(obj, attr, value)\n"
            f"        obj.save()\n"
            f"        return 200, obj\n\n"
            f'    @http_delete("/{{id}}", response={{204: None}})\n'
            f"    def delete_{singular}(self, request, id: str):\n"
            f"        {model_name}.objects.filter(id=id).delete()\n"
            f"        return 204, None\n"
        )

    # controllers/__init__.py
    (app_dir / "controllers" / "__init__.py").write_text(controller_content)

    # schemas/__init__.py — optionally with class-level docstrings
    if docstrings:
        schema_content = (
            f'"""Pydantic schemas for {name} app."""\n\n'
            "from ninja import Schema\n\n\n"
            f"class {model_name}Schema(Schema):\n"
            f'    """Read schema for {model_name} resources.\n\n'
            "    Attributes:\n"
            "        id: UUID primary key.\n"
            "        name: Display name.\n"
            "        description: Optional longer description.\n"
            '    """\n\n'
            "    id: str\n"
            "    name: str\n"
            "    description: str\n\n"
            "    class Config:\n"
            '        """Pydantic config — enable ORM mode."""\n\n'
            "        from_attributes = True\n\n\n"
            f"class Create{model_name}Schema(Schema):\n"
            f'    """Write schema used when creating or updating a {model_name}.\n\n'
            "    Attributes:\n"
            "        name: Display name (required).\n"
            "        description: Optional longer description.\n"
            '    """\n\n'
            "    name: str\n"
            '    description: str = ""\n'
        )
    else:
        schema_content = (
            f'"""Pydantic schemas for {name} app."""\n\n'
            "from ninja import Schema\n\n\n"
            f"class {model_name}Schema(Schema):\n"
            "    id: str\n"
            "    name: str\n"
            "    description: str\n\n"
            "    class Config:\n"
            "        from_attributes = True\n\n\n"
            f"class Create{model_name}Schema(Schema):\n"
            "    name: str\n"
            '    description: str = ""\n'
        )

    (app_dir / "schemas" / "__init__.py").write_text(schema_content)

    # services/__init__.py — optionally with a service class stub
    if docstrings:
        service_content = (
            f'"""Business logic services for {name} app."""\n\n'
            f"from {name}.models import {model_name}\n\n\n"
            f"class {model_name}Service:\n"
            f'    """Service layer encapsulating business logic for {model_name} resources.\n\n'
            "    Keep all non-trivial query logic and side-effects here so that\n"
            "    controllers remain thin and easy to test.\n"
            '    """\n\n'
            f"    def get_all(self) -> list[{model_name}]:\n"
            f'        """Return all {name} ordered by the model default.\n\n'
            "        Returns:\n"
            f"            A QuerySet of all {model_name} instances.\n"
            '        """\n'
            f"        return list({model_name}.objects.all())\n"
        )
    else:
        service_content = f'"""Business logic services for {name} app."""\n'

    (app_dir / "services" / "__init__.py").write_text(service_content)

    # tests/__init__.py
    (app_dir / "tests" / "__init__.py").write_text(f'"""Tests for {name} app."""\n')
    (app_dir / "tests" / f"test_{singular}.py").write_text(
        f'"""Tests for {model_name} endpoints."""\n\n'
        "import pytest\n"
        "from django.test import Client\n\n\n"
        "pytestmark = pytest.mark.django_db\n\n\n"
        f"class Test{model_name}Endpoints:\n"
        + (
            f'    """Integration tests for the {model_name} API controller."""\n\n'
            if docstrings
            else ""
        )
        + f"    def test_list_{name}(self, client: Client):\n"
        + (
            f'        """GET /api/{name}/ should return HTTP 200 with a list."""\n'
            if docstrings
            else ""
        )
        + f'        response = client.get("/api/{name}/")\n'
        + "        assert response.status_code == 200\n"
    )

    # apps.py
    (app_dir / "apps.py").write_text(
        "from django.apps import AppConfig\n\n\n"
        f"class {name.capitalize()}Config(AppConfig):\n"
        f'    default_auto_field = "django.db.models.BigAutoField"\n'
        f'    name = "{name}"\n'
    )

    # admin.py
    (app_dir / "admin.py").write_text(
        "from django.contrib import admin\n\n"
        f"from {name}.models import {model_name}\n\n\n"
        f"@admin.register({model_name})\n"
        f"class {model_name}Admin(admin.ModelAdmin):\n"
        + (f'    """Admin configuration for {model_name}."""\n\n' if docstrings else "")
        + '    list_display = ["id", "name", "created_at"]\n'
        + '    search_fields = ["name"]\n'
    )

    print_success(f"App '{name}' scaffolded at {app_dir}")
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

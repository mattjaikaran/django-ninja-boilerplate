import os
import re
import tomllib
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError
from django.core.management.commands.startapp import Command as StartAppCommand

from .generators.codegen import PACKAGE_INIT, ResourceNames, from_import
from .generators.templates.app_templates import (
    APP_LAYERS,
    DEFAULT_LAYERS,
    LAYER_PACKAGES,
    render_app_files,
)

APPS_TEMPLATE = """from django.apps import AppConfig


class {config}(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "{app_name}"
"""

WHEEL_TABLE = "[tool.hatch.build.targets.wheel]"
PACKAGES_ASSIGNMENT = re.compile(r"\s*packages\s*=")


def wheel_packages(data: dict[str, Any]) -> list[str] | None:
    """Return the Hatch wheel package list, or None when the table has none."""
    packages = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages")
    )
    return packages if isinstance(packages, list) else None


def add_wheel_package(pyproject: Path, app_name: str) -> bool:
    """Add ``app_name`` to the Hatch wheel packages list in ``pyproject``.

    Return True when the file changed. A project without a wheel packages
    list, or one that already lists the app, is left alone.
    """
    if not pyproject.is_file():
        return False
    content = pyproject.read_text(encoding="utf-8")
    packages = wheel_packages(tomllib.loads(content))
    if packages is None or app_name in packages:
        return False

    lines = content.splitlines()
    header = next(
        (i for i, line in enumerate(lines) if line.strip() == WHEEL_TABLE), None
    )
    if header is None:
        return False
    section_end = next(
        (i for i in range(header + 1, len(lines)) if lines[i].lstrip().startswith("[")),
        len(lines),
    )
    assignment = next(
        (
            i
            for i in range(header + 1, section_end)
            if PACKAGES_ASSIGNMENT.match(lines[i])
        ),
        None,
    )
    if assignment is None:
        return False

    if "]" in lines[assignment]:
        closing = lines[assignment].rindex("]")
        head = lines[assignment][:closing].rstrip()
        separator = "" if head.endswith(("[", ",")) else ","
        tail = lines[assignment][closing + 1 :]
        lines[assignment] = f'{head}{separator} "{app_name}"]{tail}'
    else:
        closing = next(i for i in range(assignment + 1, section_end) if "]" in lines[i])
        # TOML needs a comma between the current last entry and the new one.
        previous = closing - 1
        while previous > assignment and not lines[previous].strip():
            previous -= 1
        if previous > assignment and not lines[previous].rstrip().endswith(","):
            lines[previous] = f"{lines[previous].rstrip()},"
        indent = lines[closing][: len(lines[closing]) - len(lines[closing].lstrip())]
        lines.insert(closing, f'{indent}    "{app_name}",')

    updated = "\n".join(lines) + "\n"
    try:
        verified = wheel_packages(tomllib.loads(updated))
    except tomllib.TOMLDecodeError as exc:
        msg = f"Could not add {app_name!r} to {WHEEL_TABLE} in {pyproject}: {exc}"
        raise CommandError(msg) from exc
    if verified is None or app_name not in verified:
        msg = f"Could not add {app_name!r} to {WHEEL_TABLE} packages in {pyproject}"
        raise CommandError(msg)
    pyproject.write_text(updated, encoding="utf-8")
    return True


def readme_layer_blocks(names: ResourceNames, layers: str) -> tuple[str, str, str]:
    """Return the README tree and component text for the chosen layers.

    The first string is the dtos/ tree entry and the second is the
    repositories/ tree entry. The third string holds the Repositories and DTOs
    sections. A string is empty when the layer does not add it.
    """
    model = names.model_name
    snake = names.model_snake
    if layers == "service":
        return "", "", ""
    repository_tree = (
        "├── repositories/         # Data access, scoped to the owner\n"
        "│   ├── __init__.py\n"
        f"│   └── {snake}_repository.py # {model} queries for request.user\n"
    )
    if layers == "repository":
        components = (
            f"### Repositories\n\n- `{model}Repository`: Owner-scoped ORM queries.\n\n"
        )
        return "", repository_tree, components
    dto_tree = (
        "├── dtos/                 # DTOs that the repository returns\n"
        "│   ├── __init__.py\n"
        f"│   └── {snake}_dto.py    # {model}DTO read model\n"
    )
    components = (
        "### Repositories\n\n"
        f"- `{model}Repository`: Owner-scoped queries. Returns `{model}DTO` values.\n\n"
        "### DTOs\n\n"
        f"- `{model}DTO`: Frozen dataclass that the service layer reads.\n\n"
    )
    return dto_tree, repository_tree, components


class Command(StartAppCommand):
    help = "Creates a Django app directory structure with separate directories for models, admin, schemas, controllers, tests, and management commands"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--layers",
            choices=APP_LAYERS,
            default=DEFAULT_LAYERS,
            help="Data-access layers: service, repository (default), or dto.",
        )

    def handle(self, **options):
        app_name = options["name"]
        target = options.get("directory")

        if target is None:
            target = os.getcwd()

        # Call the original startapp command
        super().handle(**options)

        # Get the actual app directory
        app_directory = os.path.join(target, app_name)

        # "gadgets" and "gadget" both give model Gadget and route /gadgets.
        names = ResourceNames.from_app_name(app_name)

        # Django's template uses single quotes, which ruff rejects.
        self.create_file(
            os.path.join(app_directory, "apps.py"),
            APPS_TEMPLATE.format(config=f"{names.model_name}Config", app_name=app_name),
        )

        # Always create advanced structure regardless of the advanced flag
        # This ensures all new apps follow our organized folder pattern
        layers = options["layers"]
        created_files = self.create_advanced_structure(names, app_directory, layers)

        # An installed app missing from the wheel breaks django.setup() there.
        if add_wheel_package(Path.cwd() / "pyproject.toml", app_name):
            self.stdout.write(
                self.style.SUCCESS(
                    f'Added "{app_name}" to the Hatch wheel packages in pyproject.toml'
                )
            )

        # Print success message
        self.stdout.write(self.style.SUCCESS(f"Successfully created app '{app_name}'"))
        self.stdout.write(
            self.style.SUCCESS(
                "Created with organized folder structure: models, admin, controllers, schemas, tests"
            )
        )
        self.stdout.write(
            f"Model: {names.model_name}, controller: {names.model_name}Controller, "
            f"route: /api/{names.route}/"
        )

        # Print list of created files
        self.stdout.write("Created files:")
        for file in created_files:
            self.stdout.write(f"  - {file}")

        self.stdout.write(
            "Next: add "
            f'"{app_name}" to INSTALLED_APPS, register {names.model_name}Controller '
            "in api/urls.py, run makemigrations, then run the generated tests. "
            "`generate_feature api_endpoint` does all of this for you."
        )

    def create_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return [path]

    def create_advanced_structure(self, names, app_directory, layers):
        created_files = []
        snake = names.model_snake

        # Create directory structure
        dirs = [
            "models",
            "schemas",
            "services",
            *LAYER_PACKAGES[layers],
            "controllers",
            "admin",
            "tests",
            "management/commands",
        ]
        for dir_name in dirs:
            dir_path = os.path.join(app_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)

            # Create __init__.py files
            if "/" in dir_name:  # For nested directories like management/commands
                parent_dir = dir_name.split("/")[0]
                parent_init_path = os.path.join(
                    app_directory, parent_dir, "__init__.py"
                )
                created_files.extend(self.create_file(parent_init_path, PACKAGE_INIT))
                init_path = os.path.join(dir_path, "__init__.py")
                created_files.extend(self.create_file(init_path, PACKAGE_INIT))
            else:
                init_path = os.path.join(dir_path, "__init__.py")
                created_files.extend(
                    self.create_file(init_path, self.get_init_content(dir_name, names))
                )

        # Models, schemas, services, controllers and tests come from the shared
        # generator templates. The layer picks the data-access shape.
        rendered = render_app_files(names, layers)
        for relative_path, content in rendered.items():
            created_files.extend(
                self.create_file(
                    os.path.join(app_directory, *relative_path.split("/")), content
                )
            )

        # Create admin file
        admin_file = os.path.join(app_directory, "admin", f"{snake}_admin.py")
        created_files.extend(self.create_admin_file(names, admin_file))

        # Create management command
        command_file = os.path.join(
            app_directory,
            "management",
            "commands",
            f"generate_{names.app_name}_data.py",
        )
        created_files.extend(self.create_generate_data_command(names, command_file))

        # Create a README file
        readme_file = os.path.join(app_directory, "README.md")
        created_files.extend(self.create_readme_file(names, readme_file, layers))

        # Delete the original files that are no longer needed
        self.delete_original_files(app_directory)

        return created_files

    def delete_original_files(self, app_directory):
        """Delete the original files created by the Django startapp command that we don't need."""
        files_to_delete = ["models.py", "admin.py", "views.py", "tests.py"]
        for file_name in files_to_delete:
            file_path = os.path.join(app_directory, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

    def get_init_content(self, dir_name, names):
        app_name = names.app_name
        model_name = names.model_name
        snake = names.model_snake
        exports = {
            "models": (f"{app_name}.models.{snake}", [model_name]),
            "schemas": (
                f"{app_name}.schemas.{snake}_schema",
                [
                    f"{model_name}Schema",
                    f"Create{model_name}Schema",
                    f"Update{model_name}Schema",
                ],
            ),
            "services": (
                f"{app_name}.services.{snake}_service",
                [f"{model_name}Service"],
            ),
            "repositories": (
                f"{app_name}.repositories.{snake}_repository",
                [f"{model_name}Repository"],
            ),
            "dtos": (f"{app_name}.dtos.{snake}_dto", [f"{model_name}DTO"]),
            "controllers": (
                f"{app_name}.controllers.{snake}_controller",
                [f"{model_name}Controller"],
            ),
            "admin": (f"{app_name}.admin.{snake}_admin", [f"{model_name}Admin"]),
        }
        if dir_name not in exports:
            return PACKAGE_INIT
        module, exported = exports[dir_name]
        all_names = ", ".join(f'"{name}"' for name in exported)
        return f"{from_import(module, *exported)}\n\n__all__ = [{all_names}]\n"

    def create_admin_file(self, names, file_path):
        model_name = names.model_name
        content = f"""from django.contrib import admin
from unfold.admin import ModelAdmin

from {names.app_name}.models import {model_name}


@admin.register({model_name})
class {model_name}Admin(ModelAdmin):
    list_display = ["id", "title", "user", "created_at"]
    search_fields = ["title", "description", "user__username"]
    list_filter = ["created_at"]
"""
        return self.create_file(file_path, content)

    def create_generate_data_command(self, names, file_path):
        model_name = names.model_name
        snake = names.model_snake
        objects_name = names.route
        content = f"""from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

from {names.app_name}.models import {model_name}

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample {snake} data for testing and development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="The number of {objects_name} to create (default: 10)",
        )
        parser.add_argument(
            "--user",
            type=str,
            help="Username or email of the user to create {objects_name} for (optional)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        user_identifier = options.get("user")

        # Get or create user
        if user_identifier:
            try:
                user = User.objects.get(username=user_identifier) or User.objects.get(
                    email=user_identifier
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Creating {objects_name} for existing user: {{user.username}}"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"User with identifier {{user_identifier}} not found"
                    )
                )
                return
        # Get a random user or create one if none exist
        elif not User.objects.exists():
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            self.stdout.write(self.style.SUCCESS(f"Created new user: {{user.username}}"))
        else:
            user = User.objects.order_by("?").first()
            self.stdout.write(
                self.style.SUCCESS(f"Using existing user: {{user.username}}")
            )

        # Generate items
        items_created = 0
        for _ in range(count):
            item = {model_name}.objects.create(
                user=user,
                title=fake.sentence(nb_words=4)[:-1],  # Remove trailing period
                description=fake.paragraph(nb_sentences=3),
            )
            items_created += 1
            self.stdout.write(self.style.SUCCESS(f"Created {snake}: {{item.title}}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {{items_created}} {objects_name} for user {{user.username}}"
            )
        )
"""
        return self.create_file(file_path, content)

    def create_readme_file(self, names, file_path, layers):
        app_name = names.app_name
        model_name = names.model_name
        snake = names.model_snake
        objects_name = names.route
        dto_tree, repository_tree, layer_components = readme_layer_blocks(names, layers)
        content = f"""# {model_name} App

This app provides functionality for managing {objects_name}. The API is
mounted at `/api/{objects_name}/`.

## Folder Structure

```
{app_name}/
├── admin/                # Admin interface configurations
│   ├── __init__.py       # Imports all admin classes
│   └── {snake}_admin.py  # Admin configuration for {snake} model
├── controllers/          # API controllers/endpoints
│   ├── __init__.py       # Imports all controllers
│   └── {snake}_controller.py # {model_name}-related endpoints (JWTAuth)
{dto_tree}├── management/           # Django management commands
│   ├── __init__.py
│   └── commands/         # Custom management commands
│       ├── __init__.py
│       └── generate_{app_name}_data.py # Generates sample {snake} data
├── migrations/           # Database migrations
├── models/               # Database models
│   ├── __init__.py       # Imports all models
│   └── {snake}.py        # {model_name} model
{repository_tree}├── schemas/              # API schemas/serializers
│   ├── __init__.py       # Imports all schemas
│   └── {snake}_schema.py # {model_name}-related schemas
├── services/             # Business logic, scoped to the owner
│   ├── __init__.py       # Imports all services
│   └── {snake}_service.py # {model_name} CRUD for request.user
├── tests/                # Smoke and permission tests
│   ├── __init__.py
│   └── test_{snake}.py   # Owner list, cross-user 404, invalid payload 422
├── __init__.py           # Main app initialization
├── apps.py               # App configuration
└── README.md             # Documentation for the app
```

## Components

### Models

- `{model_name}`: Model representing a {snake} with user relationship, title, and description

### Audit logging

`{model_name}` is audited by default: every create, update and delete writes
an `AuditLog` row through `core/audit/signals.py`. If this table is
append-only or high volume, add `"{model_name}"` to `AUDIT_EXCLUDED_MODELS`
in `api/settings/common.py`. To audit only a few models, set
`AUDIT_TRACKED_MODELS` to their names. See `FEATURE_GENERATION.md`.

### Controllers

- `{model_name}Controller`: Manages CRUD operations for the authenticated user's {objects_name}. Requires `JWTAuth`.

### Services

- `{model_name}Service`: Owner-scoped queries and writes. A request for another user's {snake} returns 404.

{layer_components}### Schemas

- {model_name}-related schemas for serialization/deserialization

### Tests

One smoke and permission test file. Playwright journeys in the frontend verify the feature; see `docs/product/README.md`.

### Management Commands

- `generate_{app_name}_data`: Generates sample {snake} data for development
"""
        return self.create_file(file_path, content)

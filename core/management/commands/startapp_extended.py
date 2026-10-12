import os

from django.core.management.commands.startapp import Command as StartAppCommand

from .generators.codegen import ResourceNames, from_import
from .generators.templates.controller_templates import render_controller
from .generators.templates.model_templates import MODEL_TEMPLATE
from .generators.templates.schema_templates import SCHEMA_TEMPLATE
from .generators.templates.service_templates import render_service
from .generators.templates.test_templates import render_api_endpoint_tests

PACKAGE_INIT = (
    "# This file is intentionally left empty to make the directory a Python package.\n"
)


class Command(StartAppCommand):
    help = "Creates a Django app directory structure with separate directories for models, admin, schemas, controllers, tests, and management commands"

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

        # Always create advanced structure regardless of the advanced flag
        # This ensures all new apps follow our organized folder pattern
        created_files = self.create_advanced_structure(names, app_directory)

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

    def create_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return [path]

    def create_advanced_structure(self, names, app_directory):
        created_files = []
        snake = names.model_snake

        # Create directory structure
        dirs = [
            "models",
            "schemas",
            "services",
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

        # Models, schemas, the owner-scoped service, the controller and the
        # tests come from the shared generator templates.
        rendered = {
            os.path.join("models", f"{snake}.py"): MODEL_TEMPLATE.format(
                **names.context()
            ),
            os.path.join("schemas", f"{snake}_schema.py"): SCHEMA_TEMPLATE.format(
                **names.context()
            ),
            os.path.join("services", f"{snake}_service.py"): render_service(names),
            os.path.join("controllers", f"{snake}_controller.py"): render_controller(
                names
            ),
            os.path.join("tests", f"test_{snake}.py"): render_api_endpoint_tests(names),
        }
        for relative_path, content in rendered.items():
            created_files.extend(
                self.create_file(os.path.join(app_directory, relative_path), content)
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
        created_files.extend(self.create_readme_file(names, readme_file))

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

    def create_readme_file(self, names, file_path):
        app_name = names.app_name
        model_name = names.model_name
        snake = names.model_snake
        objects_name = names.route
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
├── management/           # Django management commands
│   ├── __init__.py
│   └── commands/         # Custom management commands
│       ├── __init__.py
│       └── generate_{app_name}_data.py # Generates sample {snake} data
├── migrations/           # Database migrations
├── models/               # Database models
│   ├── __init__.py       # Imports all models
│   └── {snake}.py        # {model_name} model
├── schemas/              # API schemas/serializers
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

### Controllers

- `{model_name}Controller`: Manages CRUD operations for the authenticated user's {objects_name}. Requires `JWTAuth`.

### Services

- `{model_name}Service`: Owner-scoped queries and writes. A request for another user's {snake} returns 404.

### Schemas

- {model_name}-related schemas for serialization/deserialization

### Tests

One smoke and permission test file. Playwright journeys in the frontend verify the feature; see `docs/product/README.md`.

### Management Commands

- `generate_{app_name}_data`: Generates sample {snake} data for development
"""
        return self.create_file(file_path, content)

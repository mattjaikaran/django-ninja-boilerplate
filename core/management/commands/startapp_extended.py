from django.core.management.commands.startapp import Command as StartAppCommand
from django.core.management.base import CommandError
from django.utils.termcolors import colorize
import os


def smart_pluralize(singular):
    # Handle specific variations
    specific_variations = {
        "blog": "Blogs",
        "message": "Messages",
        "category": "Categories",
        "history": "Histories",
    }

    if singular.lower() in specific_variations:
        return specific_variations[singular.lower()]

    # Irregular plurals
    irregulars = {
        "child": "children",
        "goose": "geese",
        "man": "men",
        "woman": "women",
        "tooth": "teeth",
        "foot": "feet",
        "mouse": "mice",
        "person": "people",
        "leaf": "leaves",
        "sheep": "sheep",
        "deer": "deer",
        "fish": "fish",
    }

    if singular.lower() in irregulars:
        return irregulars[singular.lower()]

    # Words ending in 'y'
    if singular.endswith("y"):
        if singular[-2] in "aeiou":
            return singular + "s"
        else:
            return singular[:-1] + "ies"

    # Words ending in 'is'
    if singular.endswith("is"):
        return singular[:-2] + "es"

    # Words ending in 's', 'ss', 'sh', 'ch', 'x', 'o'
    if singular.endswith(("s", "ss", "sh", "ch", "x", "o")):
        return singular + "es"

    # Default case
    return singular + "s"


def get_model_name(app_name):
    specific_models = {
        "blogs": "Blog",
        "messaging": "Message",
    }
    return specific_models.get(app_name.lower(), app_name.capitalize())


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

        # Get the model name
        model_name = get_model_name(app_name)

        # List to store created files
        created_files = []

        # Always create advanced structure regardless of the advanced flag
        # This ensures all new apps follow our organized folder pattern
        created_files.extend(
            self.create_advanced_structure(app_name, app_directory, model_name)
        )

        # Print success message
        self.stdout.write(self.style.SUCCESS(f"Successfully created app '{app_name}'"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Created with organized folder structure: models, admin, controllers, schemas, tests"
            )
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

    def create_advanced_structure(self, app_name, app_directory, model_name):
        created_files = []

        # Create directory structure
        dirs = [
            "models",
            "schemas",
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
                created_files.extend(
                    self.create_file(
                        parent_init_path,
                        "# This file is intentionally left empty to make the directory a Python package.\n",
                    )
                )
                init_path = os.path.join(dir_path, "__init__.py")
                created_files.extend(
                    self.create_file(
                        init_path,
                        "# This file is intentionally left empty to make the directory a Python package.\n",
                    )
                )
            else:
                init_path = os.path.join(dir_path, "__init__.py")
                created_files.extend(
                    self.create_file(
                        init_path, self.get_init_content(dir_name, model_name, app_name)
                    )
                )

        # Create models
        model_file = os.path.join(app_directory, "models", f"{model_name.lower()}.py")
        created_files.extend(self.create_model_file(app_name, model_file, model_name))

        # Create schemas
        schema_file = os.path.join(
            app_directory, "schemas", f"{model_name.lower()}_schema.py"
        )
        created_files.extend(self.create_schema_file(app_name, schema_file, model_name))

        # Create controller
        controller_file = os.path.join(
            app_directory, "controllers", f"{model_name.lower()}_controller.py"
        )
        created_files.extend(
            self.create_controller_file(app_name, controller_file, model_name)
        )

        # Create admin file
        admin_file = os.path.join(
            app_directory, "admin", f"{model_name.lower()}_admin.py"
        )
        created_files.extend(self.create_admin_file(app_name, admin_file, model_name))

        # Create management command
        command_file = os.path.join(
            app_directory, "management", "commands", f"generate_{app_name}_data.py"
        )
        created_files.extend(
            self.create_generate_data_command(app_name, command_file, model_name)
        )

        # Create tests
        test_file = os.path.join(
            app_directory, "tests", f"test_{model_name.lower()}.py"
        )
        created_files.extend(self.create_test_file(app_name, test_file, model_name))

        # Create a README file
        readme_file = os.path.join(app_directory, "README.md")
        created_files.extend(self.create_readme_file(app_name, readme_file, model_name))

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

    def get_init_content(self, dir_name, model_name, app_name):
        if dir_name == "models":
            return f"""from {app_name}.models.{model_name.lower()} import {model_name}

__all__ = ["{model_name}"]
"""
        elif dir_name == "schemas":
            return f"""from {app_name}.schemas.{model_name.lower()}_schema import {model_name}Schema, Create{model_name}Schema, Update{model_name}Schema

__all__ = ["{model_name}Schema", "Create{model_name}Schema", "Update{model_name}Schema"]
"""
        elif dir_name == "controllers":
            return f"""from {app_name}.controllers.{model_name.lower()}_controller import {model_name}Controller

__all__ = ["{model_name}Controller"]
"""
        elif dir_name == "admin":
            return f"""from {app_name}.admin.{model_name.lower()}_admin import {model_name}Admin

__all__ = ["{model_name}Admin"]
"""
        elif dir_name == "tests":
            return f"""from {app_name}.tests.test_{model_name.lower()} import *

__all__ = []
"""
        else:
            return "# This file is intentionally left empty to make the directory a Python package.\n"

    def create_model_file(self, app_name, file_path, model_name):
        content = f"""from django.db import models
from django.conf import settings
from core.models import AbstractBaseModel


class {model_name}(AbstractBaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="{smart_pluralize(model_name.lower())}"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "{model_name}"
        verbose_name_plural = "{smart_pluralize(model_name)}"
"""
        return self.create_file(file_path, content)

    def create_schema_file(self, app_name, file_path, model_name):
        content = f"""from ninja import Schema


class {model_name}Schema(Schema):
    id: str
    title: str
    description: str
    created_at: str
    updated_at: str


class Create{model_name}Schema(Schema):
    title: str
    description: str


class Update{model_name}Schema(Schema):
    title: str
    description: str
"""
        return self.create_file(file_path, content)

    def create_controller_file(self, app_name, file_path, model_name):
        # Converting to lowercase and pluralizing for URL
        url_name = smart_pluralize(model_name.lower())
        content = f"""import logging
from typing import List
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from {app_name}.models import {model_name}
from {app_name}.schemas import {model_name}Schema, Create{model_name}Schema, Update{model_name}Schema

logger = logging.getLogger(__name__)


@api_controller("/{url_name}", tags=["{smart_pluralize(model_name)}"])
class {model_name}Controller:
    @http_get("/all", response={{200: List[{model_name}Schema], 400: dict}})
    def list_all_{url_name}(self, request):
        try:
            items = {model_name}.objects.all()
            return 200, items
        except Exception as e:
            logger.error(f"Error listing {url_name}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/", response={{200: List[{model_name}Schema], 400: dict}})
    def list_user_{url_name}(self, request):
        try:
            user = request.user
            items = {model_name}.objects.filter(user=user)
            return 200, items
        except Exception as e:
            logger.error(f"Error listing user {url_name}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_post("/", response={{201: {model_name}Schema, 400: dict}})
    def create_{model_name.lower()}(self, request, payload: Create{model_name}Schema):
        try:
            user = request.user
            item = {model_name}.objects.create(user=user, **payload.dict())
            return 201, item
        except Exception as e:
            logger.error(f"Error creating {model_name.lower()}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/{{str:item_id}}", response={{200: {model_name}Schema, 400: dict, 404: dict}})
    def get_{model_name.lower()}(self, request, item_id: str):
        try:
            user = request.user
            item = get_object_or_404({model_name}, id=item_id, user=user)
            return 200, item
        except Exception as e:
            logger.error(f"Error getting {model_name.lower()}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_put("/{{str:item_id}}", response={{200: {model_name}Schema, 400: dict, 404: dict}})
    def update_{model_name.lower()}(self, request, item_id: str, payload: Update{model_name}Schema):
        try:
            user = request.user
            item = get_object_or_404({model_name}, id=item_id, user=user)
            for key, value in payload.dict().items():
                setattr(item, key, value)
            item.save()
            return 200, item
        except Exception as e:
            logger.error(f"Error updating {model_name.lower()}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_delete("/{{str:item_id}}", response={{204: dict, 400: dict, 404: dict}})
    def delete_{model_name.lower()}(self, request, item_id: str):
        try:
            user = request.user
            item = get_object_or_404({model_name}, id=item_id, user=user)
            item.delete()
            return 204, {{"message": "{model_name} deleted successfully"}}
        except Exception as e:
            logger.error(f"Error deleting {model_name.lower()}: {{e}}")
            return 400, {{"error": str(e)}}
"""
        return self.create_file(file_path, content)

    def create_admin_file(self, app_name, file_path, model_name):
        content = f"""from django.contrib import admin
from unfold.admin import ModelAdmin
from {app_name}.models import {model_name}


@admin.register({model_name})
class {model_name}Admin(ModelAdmin):
    list_display = ["id", "title", "user", "created_at"]
    search_fields = ["title", "description", "user__username"]
    list_filter = ["created_at"]
"""
        return self.create_file(file_path, content)

    def create_generate_data_command(self, app_name, file_path, model_name):
        # Converting to lowercase and pluralizing for variable names
        objects_name = smart_pluralize(model_name.lower())
        content = f"""from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker
from {app_name}.models import {model_name}
import random

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Generate sample {model_name.lower()} data for testing and development"

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
        else:
            # Get a random user or create one if none exist
            if not User.objects.exists():
                user = User.objects.create_user(
                    username=fake.user_name(),
                    email=fake.email(),
                    password="password123",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created new user: {{user.username}}")
                )
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
            self.stdout.write(self.style.SUCCESS(f"Created {model_name.lower()}: {{item.title}}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {{items_created}} {objects_name} for user {{user.username}}"
            )
        )
"""
        return self.create_file(file_path, content)

    def create_test_file(self, app_name, file_path, model_name):
        # Converting to lowercase and pluralizing for variable names
        objects_name = smart_pluralize(model_name.lower())
        content = f"""import pytest
from django.contrib.auth import get_user_model
from {app_name}.models import {model_name}
from core.tests.test_user import test_user, create_user
from core.tests.conftest import auth_headers

User = get_user_model()


@pytest.fixture
def {model_name.lower()}_data():
    return {{"title": "Test {model_name}", "description": "Test Description"}}


@pytest.fixture
def create_{model_name.lower()}(test_user):
    def make_{model_name.lower()}(**kwargs):
        {model_name.lower()}_data = {{
            "title": "Test {model_name}",
            "description": "Test Description",
        }}
        {model_name.lower()}_data.update(kwargs)
        return {model_name}.objects.create(user=test_user, **{model_name.lower()}_data)

    return make_{model_name.lower()}


@pytest.mark.django_db
class Test{model_name}Model:
    def test_create_{model_name.lower()}(self, test_user, {model_name.lower()}_data):
        item = {model_name}.objects.create(user=test_user, **{model_name.lower()}_data)
        assert item.title == {model_name.lower()}_data["title"]
        assert item.description == {model_name.lower()}_data["description"]
        assert item.user == test_user

    def test_{model_name.lower()}_str(self, create_{model_name.lower()}):
        item = create_{model_name.lower()}()
        assert str(item) == item.title

    def test_{model_name.lower()}_ordering(self, create_{model_name.lower()}):
        item1 = create_{model_name.lower()}(title="First {model_name}")
        item2 = create_{model_name.lower()}(title="Second {model_name}")
        items = {model_name}.objects.all()
        assert items[0] == item2  # Most recent first
        assert items[1] == item1


@pytest.mark.django_db
class Test{model_name}API:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_create_{model_name.lower()}(self, api_client, {model_name.lower()}_data, auth_headers, test_user):
        response = api_client.post(
            f"/api/{objects_name}/", {model_name.lower()}_data, content_type="application/json", **auth_headers
        )
        assert response.status_code == 201
        assert {model_name}.objects.filter(user=test_user).exists()

    def test_list_user_{objects_name}(self, api_client, create_{model_name.lower()}, auth_headers, test_user):
        create_{model_name.lower()}(title="{model_name} 1")
        create_{model_name.lower()}(title="{model_name} 2")

        # Create item for another user
        other_user = create_user(username="other", email="other@example.com")
        {model_name}.objects.create(
            user=other_user,
            title="Other's {model_name}",
            description="This shouldn't be visible",
        )

        response = api_client.get(f"/api/{objects_name}/", **auth_headers)
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2  # Only test_user's items
        assert all(item["user_id"] == str(test_user.id) for item in items)

    def test_get_{model_name.lower()}(self, api_client, create_{model_name.lower()}, auth_headers):
        item = create_{model_name.lower()}(title="Test {model_name}")
        response = api_client.get(f"/api/{objects_name}/{{item.id}}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Test {model_name}"

    def test_update_{model_name.lower()}(self, api_client, create_{model_name.lower()}, auth_headers):
        item = create_{model_name.lower()}(title="Original Title")
        update_data = {{
            "title": "Updated Title",
            "description": "Updated Description",
        }}
        response = api_client.put(
            f"/api/{objects_name}/{{item.id}}",
            update_data,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.title == update_data["title"]

    def test_delete_{model_name.lower()}(self, api_client, create_{model_name.lower()}, auth_headers):
        item = create_{model_name.lower()}()
        response = api_client.delete(f"/api/{objects_name}/{{item.id}}", **auth_headers)
        assert response.status_code == 204
        assert not {model_name}.objects.filter(id=item.id).exists()

    def test_cannot_access_others_{model_name.lower()}(self, api_client, auth_headers):
        # Create an item for another user
        other_user = create_user(username="other", email="other@example.com")
        other_item = {model_name}.objects.create(
            user=other_user,
            title="Other's {model_name}",
            description="This shouldn't be accessible",
        )

        # Try to get
        response = api_client.get(f"/api/{objects_name}/{{other_item.id}}", **auth_headers)
        assert response.status_code == 404

        # Try to update
        response = api_client.put(
            f"/api/{objects_name}/{{other_item.id}}",
            {{"title": "Hacked Title"}},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 404

        # Try to delete
        response = api_client.delete(f"/api/{objects_name}/{{other_item.id}}", **auth_headers)
        assert response.status_code == 404
        assert {model_name}.objects.filter(id=other_item.id).exists()
"""
        return self.create_file(file_path, content)

    def create_readme_file(self, app_name, file_path, model_name):
        objects_name = smart_pluralize(model_name.lower())
        content = f"""# {model_name} App

This app provides functionality for managing {objects_name}.

## Folder Structure

```
{app_name}/
├── admin/                # Admin interface configurations
│   ├── __init__.py       # Imports all admin classes
│   └── {model_name.lower()}_admin.py  # Admin configuration for {model_name.lower()} model
├── controllers/          # API controllers/endpoints
│   ├── __init__.py       # Imports all controllers
│   └── {model_name.lower()}_controller.py # {model_name}-related endpoints
├── management/           # Django management commands
│   ├── __init__.py
│   └── commands/         # Custom management commands
│       ├── __init__.py
│       └── generate_{app_name}_data.py # Generates sample {model_name.lower()} data
├── migrations/           # Database migrations
├── models/               # Database models
│   ├── __init__.py       # Imports all models
│   └── {model_name.lower()}.py        # {model_name} model
├── schemas/              # API schemas/serializers
│   ├── __init__.py       # Imports all schemas
│   └── {model_name.lower()}_schema.py # {model_name}-related schemas
├── tests/                # Unit and integration tests
│   ├── __init__.py       # Imports all tests
│   └── test_{model_name.lower()}.py   # {model_name}-related tests
├── __init__.py           # Main app initialization
├── apps.py               # App configuration
└── README.md             # Documentation for the app
```

## Components

### Models

- `{model_name}`: Model representing a {model_name.lower()} with user relationship, title, and description

### Controllers

- `{model_name}Controller`: Manages CRUD operations for {objects_name}

### Schemas

- {model_name}-related schemas for serialization/deserialization

### Tests

Comprehensive tests for the {model_name} model and API endpoints.

### Management Commands

- `generate_{app_name}_data`: Generates sample {model_name.lower()} data for development
"""
        return self.create_file(file_path, content)

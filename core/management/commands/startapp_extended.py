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
    help = "Creates a Django app directory structure with additional files for API development using Django Ninja and Django Ninja Extra"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--advanced",
            action="store_true",
            help="Create an advanced app structure with separate directories for models, schemas, and controllers",
        )

    def handle(self, **options):
        app_name = options["name"]
        target = options.get("directory")
        is_advanced = options.get("advanced", False)

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

        if is_advanced:
            # Create advanced structure
            created_files.extend(
                self.create_advanced_structure(app_name, app_directory, model_name)
            )
        else:
            # Create basic structure
            created_files.extend(
                self.create_basic_structure(app_name, app_directory, model_name)
            )

        # Print success message
        self.stdout.write(self.style.SUCCESS(f"Successfully created app '{app_name}'"))

        # Print list of created files
        self.stdout.write("Created files:")
        for file in created_files:
            self.stdout.write(f"  - {file}")

    def create_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return [path]

    def create_basic_structure(self, app_name, app_directory, model_name):
        created_files = []

        # Create basic files
        created_files.extend(self.create_api_file(app_name, app_directory, model_name))
        created_files.extend(
            self.create_schemas_file(app_name, app_directory, model_name)
        )
        created_files.extend(
            self.update_admin_file(app_name, app_directory, model_name)
        )
        created_files.extend(
            self.update_models_file(app_name, app_directory, model_name)
        )
        created_files.extend(
            self.create_generate_data_command(app_name, app_directory, model_name)
        )
        created_files.extend(self.create_test_file(app_name, app_directory, model_name))

        return created_files

    def create_advanced_structure(self, app_name, app_directory, model_name):
        created_files = []

        # Create directory structure
        dirs = ["models", "schemas", "controllers", "tests"]
        for dir_name in dirs:
            dir_path = os.path.join(app_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            init_path = os.path.join(dir_path, "__init__.py")
            created_files.extend(
                self.create_file(init_path, self.get_init_content(dir_name, model_name))
            )

        # Create models
        model_file = os.path.join(app_directory, "models", f"{model_name.lower()}.py")
        created_files.extend(self.create_model_file(app_name, model_file, model_name))

        # Create schemas
        schema_file = os.path.join(app_directory, "schemas", f"{model_name.lower()}.py")
        created_files.extend(self.create_schema_file(app_name, schema_file, model_name))

        # Create controller
        controller_file = os.path.join(
            app_directory, "controllers", f"{model_name.lower()}_controller.py"
        )
        created_files.extend(
            self.create_controller_file(app_name, controller_file, model_name)
        )

        # Create admin
        created_files.extend(
            self.update_admin_file(app_name, app_directory, model_name)
        )

        # Create management command
        created_files.extend(
            self.create_generate_data_command(app_name, app_directory, model_name)
        )

        # Create tests
        test_file = os.path.join(
            app_directory, "tests", f"test_{model_name.lower()}.py"
        )
        created_files.extend(self.create_test_file(app_name, test_file, model_name))

        return created_files

    def get_init_content(self, dir_name, model_name):
        if dir_name == "models":
            return f"""from .{model_name.lower()} import {model_name}

__all__ = ['{model_name}']
"""
        elif dir_name == "schemas":
            return f"""from .{model_name.lower()} import {model_name}Schema, {model_name}CreateSchema, {model_name}UpdateSchema

__all__ = [
    '{model_name}Schema',
    '{model_name}CreateSchema',
    '{model_name}UpdateSchema',
]
"""
        elif dir_name == "controllers":
            return f"""from .{model_name.lower()}_controller import {model_name}Controller

__all__ = ['{model_name}Controller']
"""
        else:
            return ""

    def create_model_file(self, app_name, file_path, model_name):
        content = f"""from django.db import models
import uuid
from core.models import AbstractBaseModel


# class {model_name}(AbstractBaseModel):
#     \"""
#     Model representing a {model_name.lower()}.
    
#     This model includes a UUID primary key and a name field.
#     Additional fields can be added as needed.
#     \"""
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return self.name

#     class Meta:
#         verbose_name = '{model_name}'
#         verbose_name_plural = '{smart_pluralize(model_name)}'
#         ordering = ['-date_created']
"""
        return self.create_file(file_path, content)

    def create_schema_file(self, app_name, file_path, model_name):
        content = f"""from datetime import datetime
from typing import Optional
from uuid import UUID
from ninja import Schema


# class {model_name}Schema(Schema):
#     id: UUID
#     name: str
#     description: Optional[str] = None
#     date_created: datetime
#     date_updated: datetime


# class {model_name}CreateSchema(Schema):
#     name: str
#     description: Optional[str] = None


# class {model_name}UpdateSchema(Schema):
#     name: Optional[str] = None
#     description: Optional[str] = None
"""
        return self.create_file(file_path, content)

    def create_controller_file(self, app_name, file_path, model_name):
        content = f"""from typing import List
from uuid import UUID
from ninja_extra import api_controller, http_get, http_post, http_put, http_delete
from ninja_extra.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ..models import {model_name}
from ..schemas.{model_name.lower()} import {model_name}Schema, {model_name}CreateSchema, {model_name}UpdateSchema
import logging

logger = logging.getLogger(__name__)


# @api_controller('/{app_name}', tags=['{model_name}'], permissions=[IsAuthenticated])
# class {model_name}Controller:
#     @http_get('', response={{200: List[{model_name}Schema], 500: dict}})
#     def list_{app_name}(self):
#         \"""List all {app_name}\"""
#         try:
#             items = {model_name}.objects.all()
#             return 200, items
#         except Exception as e:
#             logger.error(f"Error fetching {app_name}: {{e}}")
#             return 500, {{"error": "An error occurred while fetching list_{app_name}", "message": str(e)}}

#     @http_get('/{{item_id}}', response={{200: {model_name}Schema, 500: dict}})
#     def get_{model_name.lower()}(self, item_id: UUID):
#         \"""Get a specific {model_name.lower()}\"""
#         try:
#             item = get_object_or_404({model_name}, id=item_id)
#             return 200, item
#         except Exception as e:
#             logger.error(f"Error fetching {model_name.lower()}: {{e}}")
#             return 500, {{"error": "An error occurred while fetching get_{model_name.lower()}", "message": str(e)}}

#     @http_post('', response={{201: {model_name}Schema, 500: dict}})
#     def create_{model_name.lower()}(self, data: {model_name}CreateSchema):
#         \"""Create a new {model_name.lower()}\"""
#         try:
#             item = {model_name}.objects.create(**data.dict())
#             return 201, item
#         except Exception as e:
#             logger.error(f"Error creating {model_name.lower()}: {{e}}")
#             return 500, {{"error": "An error occurred while creating {model_name.lower()}", "message": str(e)}}

#     @http_put('/{{item_id}}', response={{200: {model_name}Schema, 500: dict}})
#     def update_{model_name.lower()}(self, item_id: UUID, data: {model_name}UpdateSchema):
#         \"""Update a {model_name.lower()}\"""
#         try:
#             item = get_object_or_404({model_name}, id=item_id)
#             for field, value in data.dict(exclude_unset=True).items():
#                 setattr(item, field, value)
#             item.save()
#             return 200, item
#         except Exception as e:
#             logger.error(f"Error updating {model_name.lower()}: {{e}}")
#             return 500, {{"error": "An error occurred while updating {model_name.lower()}", "message": str(e)}}

#     @http_delete('/{{item_id}}', response={{204: None, 500: dict}})
#     def delete_{model_name.lower()}(self, item_id: UUID):
#         \"""Delete a {model_name.lower()}\"""
#         try:
#             item = get_object_or_404({model_name}, id=item_id)
#             item.delete()
#             return 204, None
#         except Exception as e:
#             logger.error(f"Error deleting {model_name.lower()}: {{e}}")
#             return 500, {{"error": "An error occurred while deleting {model_name.lower()}", "message": str(e)}}
"""
        return self.create_file(file_path, content)

    def update_models_file(self, app_name, app_directory, model_name):
        models_file_path = os.path.join(app_directory, "models.py")
        content = f"""# {app_name}/models.py
from django.db import models
import uuid
from core.models import AbstractBaseModel


# class {model_name}(AbstractBaseModel):
#     \"""
#     Model representing a {model_name.lower()}.
    
#     This model includes a UUID primary key and a name field.
#     Additional fields can be added as needed.
#     \"""
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return self.name

#     class Meta:
#         verbose_name = '{model_name}'
#         verbose_name_plural = '{smart_pluralize(model_name)}'
#         ordering = ['-date_created']
"""
        return self.create_file(models_file_path, content)

    def update_admin_file(self, app_name, app_directory, model_name):
        admin_file_path = os.path.join(app_directory, "admin.py")
        content = f"""# {app_name}/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
# from .models import {model_name}

# TODO: Admin registration
# @admin.register({model_name})
# class {model_name}Admin(ModelAdmin):
#     list_display = ('id', 'name', 'description')
#     search_fields = ('name', 'description')
"""
        return self.create_file(admin_file_path, content)

    def create_api_file(self, app_name, app_directory, model_name):
        api_file_path = os.path.join(app_directory, "api.py")
        content = f"""# {app_name}/api.py
from ninja_extra import api_controller, http_get, http_post, http_put, http_delete
from ninja_extra.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import {model_name}
from .schemas import {model_name}Schema, {model_name}CreateSchema
from typing import List
import logging

logger = logging.getLogger(__name__)


# @api_controller('/{app_name}', tags=['{model_name}'], permissions=[IsAuthenticated])
# class {model_name}Controller:
#     @http_get('', response={{200: List[{model_name}Schema], 500: dict}})
#     def list_{app_name}(self):
#         \"""List all {app_name}\"""
#         try:
#             items = {model_name}.objects.all()
#             return 200, items
#         except Exception as e:
#             logger.error(f"Error fetching {app_name}: {{e}}")
#             return 500, {{"error": "An error occurred while fetching {app_name}", "message": str(e)}}
"""
        return self.create_file(api_file_path, content)

    def create_schemas_file(self, app_name, app_directory, model_name):
        schemas_file_path = os.path.join(app_directory, "schemas.py")
        content = f"""# {app_name}/schemas.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from ninja import Schema


# class {model_name}Schema(Schema):
#     id: UUID
#     name: str
#     description: Optional[str] = None
#     date_created: datetime
#     date_updated: datetime


# class {model_name}CreateSchema(Schema):
#     name: str
#     description: Optional[str] = None


# class {model_name}UpdateSchema(Schema):
#     name: Optional[str] = None
#     description: Optional[str] = None
"""
        return self.create_file(schemas_file_path, content)

    def create_generate_data_command(self, app_name, app_directory, model_name):
        command_dir = os.path.join(app_directory, "management", "commands")
        os.makedirs(command_dir, exist_ok=True)
        command_file_path = os.path.join(command_dir, f"generate_{app_name}_data.py")
        content = f"""# {app_name}/management/commands/generate_{app_name}_data.py
from django.core.management.base import BaseCommand
from {app_name}.models import {model_name}
from django.utils.crypto import get_random_string


# class Command(BaseCommand):
#     help = 'Generate sample data for {model_name}'

#     def add_arguments(self, parser):
#         parser.add_argument('count', type=int, help='Number of {model_name.lower()} to create')

#     def handle(self, *args, **options):
#         count = options['count']
#         for i in range(count):
#             {model_name}.objects.create(
#                 name=f'{model_name} {{get_random_string(5)}}',
#                 description=f'Description for {model_name.lower()} {{i+1}}'
#             )
#         self.stdout.write(self.style.SUCCESS(f'Successfully created {{count}} {model_name.lower()}'))
"""
        return self.create_file(command_file_path, content)

    def create_test_file(self, app_name, app_directory, model_name):
        test_file_path = os.path.join(app_directory, "tests.py")
        content = f"""# {app_name}/tests.py
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import {model_name}


# class {model_name}Tests(APITestCase):
#     def setUp(self):
#         self.{model_name.lower()} = {model_name}.objects.create(
#             name='Test {model_name}',
#             description='Test Description'
#         )

#     def test_create_{model_name.lower()}(self):
#         \"""Test creating a new {model_name.lower()}\"""
#         url = reverse('{app_name}-list')
#         data = {{
#             'name': 'New {model_name}',
#             'description': 'New Description'
#         }}
#         response = self.client.post(url, data, format='json')
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual({model_name}.objects.count(), 2)

#     def test_get_{model_name.lower()}_list(self):
#         \"""Test getting list of {model_name.lower()}\"""
#         url = reverse('{app_name}-list')
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data), 1)
"""
        return self.create_file(test_file_path, content)

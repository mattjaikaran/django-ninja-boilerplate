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

        # Create additional files
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

        # Print success message
        self.stdout.write(self.style.SUCCESS(f"Successfully created app '{app_name}'"))

        # Print list of created files
        self.stdout.write("Created files:")
        for file in created_files:
            self.stdout.write(f"  - {file}")

    def create_file(self, path, content):
        with open(path, "w") as f:
            f.write(content)
        return [path]

    def update_models_file(self, app_name, app_directory, model_name):
        models_file_path = os.path.join(app_directory, "models.py")
        content = f"""# {app_name}/models.py
from django.db import models
import uuid

class {model_name}(models.Model):
    \"""
    Model representing a {model_name.lower()}.
    
    This model includes a UUID primary key and a name field.
    Additional fields can be added as needed.
    \"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = '{model_name}'
        verbose_name_plural = '{smart_pluralize(model_name)}'
"""
        return self.create_file(models_file_path, content)

    def update_admin_file(self, app_name, app_directory, model_name):
        admin_file_path = os.path.join(app_directory, "admin.py")
        content = f"""# {app_name}/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import {model_name}

@admin.register({model_name})
class {model_name}Admin(ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name', 'description')
"""
        return self.create_file(admin_file_path, content)

    def create_api_file(self, app_name, app_directory, model_name):
        api_file_path = os.path.join(app_directory, "api.py")
        content = f"""# {app_name}/api.py
from ninja_extra import api_controller, http_get, http_post, http_put, http_delete
from .models import {model_name}
from .schemas import {model_name}Schema, {model_name}CreateSchema

@api_controller('/{app_name}', tags=['{model_name}'])
class {model_name}API:
    @http_get('/', response=list[{model_name}Schema])
    def list_{app_name}(self):
        return {model_name}.objects.all()

    @http_post('/', response={model_name}Schema)
    def create_{app_name}(self, payload: {model_name}CreateSchema):
        return {model_name}.objects.create(**payload.dict())

    @http_get('/{{id}}', response={model_name}Schema)
    def get_{app_name}(self, id: str):
        return {model_name}.objects.get(id=id)

    @http_put('/{{id}}', response={model_name}Schema)
    def update_{app_name}(self, id: str, payload: {model_name}CreateSchema):
        {app_name} = {model_name}.objects.get(id=id)
        for attr, value in payload.dict().items():
            setattr({app_name}, attr, value)
        {app_name}.save()
        return {app_name}

    @http_delete('/{{id}}')
    def delete_{app_name}(self, id: str):
        {model_name}.objects.get(id=id).delete()
        return {{"success": True}}
"""
        return self.create_file(api_file_path, content)

    def create_schemas_file(self, app_name, app_directory, model_name):
        schemas_file_path = os.path.join(app_directory, "schemas.py")
        content = f"""# {app_name}/schemas.py
from ninja import Schema
from typing import Optional
from uuid import UUID

class {model_name}Schema(Schema):
    id: UUID
    name: str
    description: Optional[str] = None

class {model_name}CreateSchema(Schema):
    name: str
    description: Optional[str] = None
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

class Command(BaseCommand):
    help = 'Generate sample data for {model_name}'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, help='Number of {model_name.lower()} to create')

    def handle(self, *args, **options):
        count = options['count']
        for i in range(count):
            {model_name}.objects.create(
                name=f'{model_name} {{get_random_string(5)}}',
                description=f'Description for {model_name.lower()} {{i+1}}'
            )
        self.stdout.write(self.style.SUCCESS(f'Successfully created {{count}} {model_name.lower()}'))
"""
        return self.create_file(command_file_path, content)

    def create_test_file(self, app_name, app_directory, model_name):
        test_file_path = os.path.join(app_directory, "tests.py")
        content = f"""# {app_name}/tests.py
from django.test import TestCase
from .models import {model_name}

class {model_name}Tests(TestCase):
    def setUp(self):
        self.{app_name} = {model_name}.objects.create(
            name='Test {model_name}',
            description='This is a test description'
        )

    def test_str(self):
        self.assertEqual(str(self.{app_name}), 'Test {model_name}')

    def test_model_fields(self):
        self.assertTrue(isinstance(self.{app_name}.name, str))
        self.assertTrue(isinstance(self.{app_name}.description, str))

    def test_api_list(self):
        response = self.client.get(f'/{app_name}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_api_detail(self):
        response = self.client.get(f'/{app_name}/{{self.{app_name}.id}}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Test {model_name}')
"""
        return self.create_file(test_file_path, content)

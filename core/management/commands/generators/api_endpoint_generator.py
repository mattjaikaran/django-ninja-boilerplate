"""API endpoint generator for rapid CRUD development."""

from .base_generator import BaseGenerator
from .templates.controller_templates import CONTROLLER_TEMPLATE
from .templates.model_templates import MODEL_TEMPLATE
from .templates.schema_templates import SCHEMA_TEMPLATE


class ApiEndpointGenerator(BaseGenerator):
    """Generator for complete API endpoint with CRUD operations."""

    def generate(self) -> None:
        """Generate the API endpoint feature."""
        self.logger.info(f"Generating API endpoint feature for {self.app_name}...")

        # Create Django app
        self.create_django_app()

        # Generate files
        self._generate_models()
        self._generate_schemas()
        self._generate_controllers()
        self._generate_admin()
        self._generate_tests()

        # Update project files
        self._update_settings()
        self._update_urls()

        self.logger.info(
            f"Successfully generated API endpoint feature for {self.app_name}"
        )

    def _generate_models(self) -> None:
        """Generate model files."""
        model_content = MODEL_TEMPLATE.format(
            app_name=self.app_name,
            app_name_title=self.app_name.title(),
            model_name=self.app_name.title().rstrip("s"),
        )

        models_dir = self.app_path / "models"
        models_dir.mkdir(exist_ok=True)

        self.create_file(models_dir / f"{self.app_name.rstrip('s')}.py", model_content)
        self.create_file(
            models_dir / "__init__.py",
            f'from .{self.app_name.rstrip("s")} import {self.app_name.title().rstrip("s")}\n\n__all__ = ["{self.app_name.title().rstrip("s")}"]',
        )

    def _generate_schemas(self) -> None:
        """Generate schema files."""
        schema_content = SCHEMA_TEMPLATE.format(
            app_name=self.app_name,
            app_name_title=self.app_name.title(),
            model_name=self.app_name.title().rstrip("s"),
        )

        schemas_dir = self.app_path / "schemas"
        schemas_dir.mkdir(exist_ok=True)

        self.create_file(
            schemas_dir / f"{self.app_name.rstrip('s')}_schema.py", schema_content
        )
        self.create_file(
            schemas_dir / "__init__.py",
            f"from .{self.app_name.rstrip('s')}_schema import *",
        )

    def _generate_controllers(self) -> None:
        """Generate controller files."""
        controller_content = CONTROLLER_TEMPLATE.format(
            app_name=self.app_name,
            app_name_title=self.app_name.title(),
            model_name=self.app_name.title().rstrip("s"),
            model_name_lower=self.app_name.rstrip("s"),
        )

        controllers_dir = self.app_path / "controllers"
        controllers_dir.mkdir(exist_ok=True)

        self.create_file(
            controllers_dir / f"{self.app_name.rstrip('s')}_controller.py",
            controller_content,
        )
        self.create_file(
            controllers_dir / "__init__.py",
            f'from .{self.app_name.rstrip("s")}_controller import {self.app_name.title().rstrip("s")}Controller\n\n__all__ = ["{self.app_name.title().rstrip("s")}Controller"]',
        )

    def _generate_admin(self) -> None:
        """Generate admin files."""
        admin_content = f'''"""Admin configuration for {self.app_name}."""

from django.contrib import admin

from ..models import {self.app_name.title().rstrip("s")}


@admin.register({self.app_name.title().rstrip("s")})
class {self.app_name.title().rstrip("s")}Admin(admin.ModelAdmin):
    """Admin interface for {self.app_name.title().rstrip("s")} model."""

    list_display = ["id", "name", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
'''

        admin_dir = self.app_path / "admin"
        admin_dir.mkdir(exist_ok=True)

        self.create_file(
            admin_dir / f"{self.app_name.rstrip('s')}_admin.py", admin_content
        )
        self.create_file(
            admin_dir / "__init__.py",
            f"from .{self.app_name.rstrip('s')}_admin import {self.app_name.title().rstrip('s')}Admin",
        )

    def _generate_tests(self) -> None:
        """Generate test files."""
        test_content = f'''"""Tests for {self.app_name} API."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client

from {self.app_name}.models import {self.app_name.title().rstrip("s")}

User = get_user_model()


@pytest.mark.django_db
class Test{self.app_name.title().rstrip("s")}API:
    """Test cases for {self.app_name.title().rstrip("s")} API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_{self.app_name.rstrip("s")}(self):
        """Test creating a new {self.app_name.rstrip("s")}."""
        url = reverse("{self.app_name.rstrip("s")}-list")
        data = {{"name": "Test {self.app_name.title().rstrip("s")}"}}

        response = self.client.post(url, data)

        assert response.status_code == 201
        assert {self.app_name.title().rstrip("s")}.objects.count() == 1

    def test_list_{self.app_name}(self):
        """Test listing {self.app_name}."""
        # Create test data
        {self.app_name.title().rstrip("s")}.objects.create(name="Test {self.app_name.title().rstrip("s")}")

        url = reverse("{self.app_name.rstrip("s")}-list")
        response = self.client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 1

    def test_retrieve_{self.app_name.rstrip("s")}(self):
        """Test retrieving a specific {self.app_name.rstrip("s")}."""
        obj = {self.app_name.title().rstrip("s")}.objects.create(name="Test {self.app_name.title().rstrip("s")}")

        url = reverse("{self.app_name.rstrip("s")}-detail", kwargs={{"pk": obj.pk}})
        response = self.client.get(url)

        assert response.status_code == 200
        assert response.data["name"] == "Test {self.app_name.title().rstrip("s")}"

    def test_update_{self.app_name.rstrip("s")}(self):
        """Test updating a {self.app_name.rstrip("s")}."""
        obj = {self.app_name.title().rstrip("s")}.objects.create(name="Test {self.app_name.title().rstrip("s")}")

        url = reverse("{self.app_name.rstrip("s")}-detail", kwargs={{"pk": obj.pk}})
        data = {{"name": "Updated {self.app_name.title().rstrip("s")}"}}
        response = self.client.put(url, data)

        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.name == "Updated {self.app_name.title().rstrip("s")}"

    def test_delete_{self.app_name.rstrip("s")}(self):
        """Test deleting a {self.app_name.rstrip("s")}."""
        obj = {self.app_name.title().rstrip("s")}.objects.create(name="Test {self.app_name.title().rstrip("s")}")

        url = reverse("{self.app_name.rstrip("s")}-detail", kwargs={{"pk": obj.pk}})
        response = self.client.delete(url)

        assert response.status_code == 204
        assert {self.app_name.title().rstrip("s")}.objects.count() == 0
'''

        tests_dir = self.app_path / "tests"
        tests_dir.mkdir(exist_ok=True)

        self.create_file(
            tests_dir / f"test_{self.app_name.rstrip('s')}_api.py", test_content
        )
        self.create_file(tests_dir / "__init__.py", "")

    def _update_settings(self) -> None:
        """Update Django settings."""
        self.update_settings(self.app_name, {})

    def _update_urls(self) -> None:
        """Update URL configuration."""
        self.update_urls(self.app_name)

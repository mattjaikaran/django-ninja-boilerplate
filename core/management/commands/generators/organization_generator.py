"""Organization feature generator."""

from .base_generator import BaseGenerator


class OrganizationGenerator(BaseGenerator):
    """Generator for organization management feature."""

    def __init__(
        self,
        app_name: str = "organizations",
        platform_type: str = "b2b",
        minimal: bool = False,
    ):
        """Initialize the organization generator."""
        super().__init__(app_name, minimal)
        self.platform_type = platform_type

    def generate(self) -> None:
        """Generate the organization feature."""
        print(f"Generating organization feature for {self.platform_type} platform...")

        # Create Django app
        self.create_django_app()

        # Generate models
        self._generate_models()

        # Generate schemas
        self._generate_schemas()

        # Generate services
        self._generate_services()

        # Generate controllers
        self._generate_controllers()

        # Generate admin
        self._generate_admin()

        # Generate tests
        self._generate_tests()

        # Update settings
        self._update_settings()

        # Update URLs
        self.update_urls(self.app_name)

        # Create migrations
        self.create_migration()

        print("Organization feature generated successfully!")

    def _generate_models(self) -> None:
        """Generate organization models."""
        from .templates.model_templates import ORGANIZATION_MODELS_TEMPLATE

        self.create_file(
            self.app_path / "models" / "organization.py", ORGANIZATION_MODELS_TEMPLATE
        )

        # Update models __init__.py
        init_content = """from .organization import Organization, OrganizationMember

__all__ = ["Organization", "OrganizationMember"]
"""
        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _generate_schemas(self) -> None:
        """Generate organization schemas."""
        from .templates.schema_templates import ORGANIZATION_SCHEMAS_TEMPLATE

        self.create_file(
            self.app_path / "schemas" / "organization_schema.py",
            ORGANIZATION_SCHEMAS_TEMPLATE,
        )

    def _generate_services(self) -> None:
        """Generate organization services."""
        from .templates.service_templates import ORGANIZATION_SERVICE_TEMPLATE

        self.create_file(
            self.app_path / "services" / "__init__.py", "# Organization services"
        )
        self.create_file(
            self.app_path / "services" / "organization_service.py",
            ORGANIZATION_SERVICE_TEMPLATE,
        )

    def _generate_controllers(self) -> None:
        """Generate organization controllers."""
        from .templates.organization_controller_template import (
            ORGANIZATION_CONTROLLER_TEMPLATE,
        )

        controller_content = ORGANIZATION_CONTROLLER_TEMPLATE.format(
            app_name=self.app_name
        )

        self.create_file(
            self.app_path / "controllers" / "organization_controller.py",
            controller_content,
        )

    def _generate_admin(self) -> None:
        """Generate organization admin."""
        from .templates.admin_templates import ORGANIZATION_ADMIN_TEMPLATE

        admin_content = ORGANIZATION_ADMIN_TEMPLATE.format(app_name=self.app_name)
        self.create_file(
            self.app_path / "admin" / "organization_admin.py", admin_content
        )

    def _generate_tests(self) -> None:
        """Generate organization tests."""
        from .templates.test_templates import ORGANIZATION_TESTS_TEMPLATE

        tests_content = ORGANIZATION_TESTS_TEMPLATE.format(app_name=self.app_name)
        self.create_file(
            self.app_path / "tests" / "test_organization.py", tests_content
        )

    def _update_settings(self) -> None:
        """Update Django settings for organizations."""
        settings_updates = {
            "ORGANIZATION_INVITATION_EXPIRY_DAYS": 7,
            "ORGANIZATION_MAX_MEMBERS": 100 if self.minimal else 1000,
        }
        self.update_settings(self.app_name, settings_updates)

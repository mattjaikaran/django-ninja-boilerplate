"""RBAC (Role-Based Access Control) feature generator."""

from .base_generator import BaseGenerator


class RBACGenerator(BaseGenerator):
    """Generator for RBAC feature."""

    def __init__(
        self,
        app_name: str = "rbac",
        platform_type: str = "b2c",
        minimal: bool = False,
    ):
        """Initialize the RBAC generator.

        Args:
            app_name: Name of the Django app to create
            platform_type: Platform type (b2c, b2b, marketplace, saas)
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal)
        self.platform_type = platform_type

    def generate(self) -> None:
        """Generate the RBAC feature."""
        print(f"Generating RBAC feature for {self.platform_type} platform...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        # Generate models
        self._generate_models()

        # Generate permissions system
        self._generate_permissions()

        # Generate decorators
        self._generate_decorators()

        # Generate middleware
        self._generate_middleware()

        # Generate schemas
        self._generate_schemas()

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

        print("RBAC feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = []
        if not self.minimal:
            dependencies.extend(
                [
                    "django-guardian>=2.4.0",
                    "django-rules>=3.3.0",
                ]
            )
        self.update_pyproject_toml(dependencies)

    def _generate_models(self) -> None:
        """Generate RBAC models."""
        models_content = self._get_models_content()
        self.create_file(self.app_path / "models" / "rbac.py", models_content)

        # Update models __init__.py
        init_content = """from .rbac import Role, Permission, UserRole, RolePermission

__all__ = ["Role", "Permission", "UserRole", "RolePermission"]
"""
        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _get_models_content(self) -> str:
        """Get the RBAC models content."""
        from .templates.model_templates import RBAC_MODELS_TEMPLATE

        return RBAC_MODELS_TEMPLATE

    def _generate_permissions(self) -> None:
        """Generate permissions system."""
        from .templates.service_templates import RBAC_SERVICE_TEMPLATE

        self.create_file(self.app_path / "services" / "__init__.py", "# RBAC services")
        self.create_file(
            self.app_path / "services" / "rbac_service.py", RBAC_SERVICE_TEMPLATE
        )

    def _generate_decorators(self) -> None:
        """Generate RBAC decorators."""
        from .templates.decorator_templates import RBAC_DECORATORS_TEMPLATE

        self.create_file(self.app_path / "decorators.py", RBAC_DECORATORS_TEMPLATE)

    def _generate_middleware(self) -> None:
        """Generate RBAC middleware."""
        from .templates.decorator_templates import RBAC_MIDDLEWARE_TEMPLATE

        self.create_file(self.app_path / "middleware.py", RBAC_MIDDLEWARE_TEMPLATE)

    def _generate_schemas(self) -> None:
        """Generate RBAC schemas."""
        from .templates.schema_templates import RBAC_SCHEMAS_TEMPLATE

        self.create_file(
            self.app_path / "schemas" / "rbac_schema.py", RBAC_SCHEMAS_TEMPLATE
        )

    def _generate_controllers(self) -> None:
        """Generate RBAC controllers."""
        from .templates.controller_templates import RBAC_CONTROLLER_TEMPLATE

        controllers_content = RBAC_CONTROLLER_TEMPLATE.format(app_name=self.app_name)

        self.create_file(
            self.app_path / "controllers" / "rbac_controller.py", controllers_content
        )

    def _generate_admin(self) -> None:
        """Generate RBAC admin."""
        from .templates.admin_templates import RBAC_ADMIN_TEMPLATE

        admin_content = RBAC_ADMIN_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "admin" / "rbac_admin.py", admin_content)

    def _generate_tests(self) -> None:
        """Generate RBAC tests."""
        from .templates.test_templates import RBAC_TESTS_TEMPLATE

        tests_content = RBAC_TESTS_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "tests" / "test_rbac.py", tests_content)

    def _update_settings(self) -> None:
        """Update Django settings for RBAC."""
        settings_updates = {
            "RBAC_AUTO_CREATE_DEFAULT_ROLES": True,
            "RBAC_DEFAULT_ROLE": "user",
        }
        self.update_settings(self.app_name, settings_updates)

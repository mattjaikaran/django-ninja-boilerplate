"""RBAC (Role-Based Access Control) feature generator.

Role and permission management is staff-only (IsAdminUser). A regular user
reads only their own roles and permissions at GET /rbac/me/permissions.
"""

from .base_generator import BaseGenerator
from .codegen import from_import, import_block, package_init
from .templates.admin_templates import RBAC_ADMIN_TEMPLATE
from .templates.controller_templates import RBAC_CONTROLLER_TEMPLATE
from .templates.decorator_templates import (
    RBAC_DECORATORS_TEMPLATE,
    RBAC_MIDDLEWARE_TEMPLATE,
)
from .templates.model_templates import RBAC_MODELS_TEMPLATE
from .templates.schema_templates import RBAC_SCHEMAS_TEMPLATE
from .templates.service_templates import RBAC_SERVICE_TEMPLATE
from .templates.test_templates import RBAC_TESTS_TEMPLATE

MODEL_NAMES = ["Permission", "Role", "RolePermission", "UserRole"]
SCHEMA_NAMES = [
    "PermissionSchema",
    "CreatePermissionSchema",
    "RoleSchema",
    "CreateRoleSchema",
    "UpdateRoleSchema",
    "UserRoleSchema",
    "AssignRoleSchema",
    "UserPermissionsSchema",
]


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

        self.create_django_app()
        self.remove_scaffold()
        self._generate_models()
        self._generate_schemas()
        self._generate_services()
        self._generate_decorators()
        self._generate_middleware()
        self._generate_controllers()
        self._generate_admin()
        self._generate_tests()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "RBACController")
        self.create_migration()

        print("RBAC feature generated successfully!")

    def _service_import(self) -> str:
        return from_import(f"{self.app_name}.services", "RBACService")

    def _generate_models(self) -> None:
        """Generate RBAC models."""
        self.create_file(self.app_path / "models" / "rbac.py", RBAC_MODELS_TEMPLATE)
        self.create_file(
            self.app_path / "models" / "__init__.py",
            package_init((f"{self.app_name}.models.rbac", MODEL_NAMES)),
        )

    def _generate_schemas(self) -> None:
        """Generate RBAC schemas."""
        self.create_file(
            self.app_path / "schemas" / "rbac_schema.py", RBAC_SCHEMAS_TEMPLATE
        )
        self.create_file(
            self.app_path / "schemas" / "__init__.py",
            package_init((f"{self.app_name}.schemas.rbac_schema", SCHEMA_NAMES)),
        )

    def _generate_services(self) -> None:
        """Generate the RBAC service."""
        app = self.app_name
        first_party_imports = import_block(
            from_import("api.exceptions", "ConflictError", "ValidationError"),
            from_import(f"{app}.models", "Permission", "Role", "UserRole"),
            from_import(
                f"{app}.schemas",
                "CreatePermissionSchema",
                "CreateRoleSchema",
                "UpdateRoleSchema",
            ),
        )
        self.create_file(
            self.app_path / "services" / "rbac_service.py",
            RBAC_SERVICE_TEMPLATE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            self.app_path / "services" / "__init__.py",
            package_init((f"{app}.services.rbac_service", ["RBACService"])),
        )

    def _generate_decorators(self) -> None:
        """Generate RBAC decorators."""
        first_party_imports = import_block(
            from_import("api.exceptions", "APIPermissionError", "AuthenticationError"),
            self._service_import(),
        )
        self.create_file(
            self.app_path / "decorators.py",
            RBAC_DECORATORS_TEMPLATE.format(first_party_imports=first_party_imports),
        )

    def _generate_middleware(self) -> None:
        """Generate RBAC middleware."""
        self.create_file(
            self.app_path / "middleware.py",
            RBAC_MIDDLEWARE_TEMPLATE.format(first_party_imports=self._service_import()),
        )

    def _generate_controllers(self) -> None:
        """Generate the RBAC controller."""
        app = self.app_name
        first_party_imports = import_block(
            "from api.decorators import log_api_call",
            from_import("api.permissions", "IsAdminUser", "IsAuthenticated"),
            from_import(f"{app}.schemas", *SCHEMA_NAMES),
            self._service_import(),
        )
        self.create_file(
            self.app_path / "controllers" / "rbac_controller.py",
            RBAC_CONTROLLER_TEMPLATE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            self.app_path / "controllers" / "__init__.py",
            package_init((f"{app}.controllers.rbac_controller", ["RBACController"])),
        )

    def _generate_admin(self) -> None:
        """Generate RBAC admin."""
        app = self.app_name
        self.create_file(
            self.app_path / "admin" / "rbac_admin.py",
            RBAC_ADMIN_TEMPLATE.format(
                first_party_imports=from_import(f"{app}.models", *MODEL_NAMES)
            ),
        )
        admin_classes = [
            "PermissionAdmin",
            "RoleAdmin",
            "RolePermissionAdmin",
            "UserRoleAdmin",
        ]
        self.create_file(
            self.app_path / "admin" / "__init__.py",
            package_init((f"{app}.admin.rbac_admin", admin_classes)),
        )

    def _generate_tests(self) -> None:
        """Generate the RBAC smoke and permission tests."""
        app = self.app_name
        first_party_imports = import_block(
            from_import(f"{app}.models", "Permission", "Role", "UserRole"),
            "from tests.utils.assertions import assert_validation_error",
        )
        self.create_file(
            self.app_path / "tests" / "test_rbac.py",
            RBAC_TESTS_TEMPLATE.format(
                app_name=app, first_party_imports=first_party_imports
            ),
        )

"""Redis/Valkey cache feature generator.

The app has no models and adds no settings or dependencies: it works through
Django's cache framework, so it uses the ``CACHES`` backend that
``api/settings`` builds from ``REDIS_URL``/``VALKEY_URL``. Its controller is
staff-only (IsAdminUser) because cache keys can hold session data and tokens.
"""

from .base_generator import BaseGenerator
from .codegen import fill_imports, from_import, package_init
from .templates.redis_templates import (
    CACHE_CONTROLLER_TEMPLATE,
    CACHE_SCHEMAS_TEMPLATE,
    CACHE_SERVICE_TEMPLATE,
    CACHE_TESTS_TEMPLATE,
)


class RedisGenerator(BaseGenerator):
    """Generator for the Redis/Valkey cache feature."""

    def __init__(
        self,
        app_name: str = "cache",
        minimal: bool = False,
    ):
        """Initialize the Redis generator.

        Args:
            app_name: Name of the Django app to create
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal)

    def generate(self) -> None:
        """Generate the cache feature."""
        print("Generating Redis/Valkey cache feature...")

        self.create_django_app()
        self.remove_scaffold()
        self._generate_schemas()
        self._generate_services()
        self._generate_controllers()
        self._generate_tests()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "CacheController")

        print("Redis/Valkey cache feature generated successfully!")

    def _generate_schemas(self) -> None:
        """Generate the cache schemas."""
        self.create_file(
            self.app_path / "schemas" / "cache_schema.py", CACHE_SCHEMAS_TEMPLATE
        )
        self.create_file(
            self.app_path / "schemas" / "__init__.py",
            package_init(
                (f"{self.app_name}.schemas.cache_schema", ["CacheHealthSchema"])
            ),
        )

    def _generate_services(self) -> None:
        """Generate the cache service."""
        app = self.app_name
        self.create_file(
            self.app_path / "services" / "cache_service.py",
            fill_imports(
                CACHE_SERVICE_TEMPLATE,
                from_import("api.exceptions", "ExternalServiceError", "NotFoundError"),
            ),
        )
        self.create_file(
            self.app_path / "services" / "__init__.py",
            package_init((f"{app}.services.cache_service", ["CacheService"])),
        )

    def _generate_controllers(self) -> None:
        """Generate the staff-only cache controller."""
        app = self.app_name
        self.create_file(
            self.app_path / "controllers" / "cache_controller.py",
            fill_imports(
                CACHE_CONTROLLER_TEMPLATE,
                "from api.decorators import log_api_call",
                "from api.permissions import IsAdminUser",
                from_import(f"{app}.schemas", "CacheHealthSchema"),
                from_import(f"{app}.services", "CacheService"),
            ),
        )
        self.create_file(
            self.app_path / "controllers" / "__init__.py",
            package_init((f"{app}.controllers.cache_controller", ["CacheController"])),
        )

    def _generate_tests(self) -> None:
        """Generate the cache smoke and permission tests."""
        self.create_file(
            self.app_path / "tests" / "test_cache.py", CACHE_TESTS_TEMPLATE
        )

"""API endpoint generator for rapid CRUD development."""

from .base_generator import BaseGenerator, GeneratorError
from .codegen import ResourceNames


class ApiEndpointGenerator(BaseGenerator):
    """Generator for complete API endpoint with CRUD operations.

    ``startapp_extended`` renders the app from the shared templates (model,
    schemas, owner-scoped service, ``JWTAuth`` controller and tests). This
    generator creates that app and registers it in the project.
    """

    def generate(self) -> None:
        """Generate the API endpoint feature."""
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        self.logger.info("Generating API endpoint feature for %s...", self.app_name)
        names = ResourceNames.from_app_name(self.app_name)

        self.create_django_app()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, f"{names.model_name}Controller")
        self.create_migration()

        self.logger.info(
            "Successfully generated API endpoint feature for %s at /api/%s/",
            self.app_name,
            names.route,
        )

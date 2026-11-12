"""API endpoint generator for rapid CRUD development."""

import subprocess
import sys

from .base_generator import BaseGenerator, GeneratorError
from .codegen import ResourceNames
from .templates.app_templates import DEFAULT_LAYERS


class ApiEndpointGenerator(BaseGenerator):
    """Generator for complete API endpoint with CRUD operations.

    ``startapp_extended`` renders the app from the shared templates (model,
    schemas, owner-scoped service, ``JWTAuth`` controller and tests). This
    generator creates that app and registers it in the project.
    """

    def __init__(
        self, app_name: str, minimal: bool = False, layers: str = DEFAULT_LAYERS
    ) -> None:
        """Store the app name, scaffold mode and layer set."""
        super().__init__(app_name, minimal=minimal)
        self.layers = layers

    def create_django_app(self) -> None:
        """Create the app with startapp_extended and the chosen layers."""
        try:
            subprocess.run(
                [
                    sys.executable,
                    "manage.py",
                    "startapp_extended",
                    self.app_name,
                    "--layers",
                    self.layers,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info("Successfully created Django app: %s", self.app_name)
            self.created_app = True
        except subprocess.CalledProcessError as e:
            self.logger.exception("Failed to create Django app: %s", e.stderr)
            msg = f"Failed to create Django app: {e.stderr}"
            raise GeneratorError(msg) from e

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

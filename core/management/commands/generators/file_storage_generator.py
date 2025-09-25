"""File storage feature generator."""

from .base_generator import BaseGenerator


class FileStorageGenerator(BaseGenerator):
    """Generator for file storage feature."""

    def __init__(
        self,
        app_name: str = "files",
        provider: str = "local",
        minimal: bool = False,
    ):
        """Initialize the file storage generator."""
        super().__init__(app_name, minimal)
        self.provider = provider

    def generate(self) -> None:
        """Generate the file storage feature."""
        print(f"Generating file storage feature with {self.provider} provider...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        print("File storage feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = []

        if self.provider == "aws":
            dependencies.append("boto3>=1.35.0")
        elif self.provider == "gcp":
            dependencies.append("google-cloud-storage>=2.10.0")

        if not self.minimal:
            dependencies.extend(
                [
                    "Pillow>=10.4.0",
                    "python-magic>=0.4.0",
                ]
            )

        self.update_pyproject_toml(dependencies)

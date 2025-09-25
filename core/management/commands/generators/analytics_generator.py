"""Analytics feature generator."""

from .base_generator import BaseGenerator


class AnalyticsGenerator(BaseGenerator):
    """Generator for analytics tracking feature."""

    def __init__(
        self,
        app_name: str = "analytics",
        minimal: bool = False,
    ):
        """Initialize the analytics generator."""
        super().__init__(app_name, minimal)

    def generate(self) -> None:
        """Generate the analytics feature."""
        print("Generating analytics tracking feature...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        print("Analytics feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = []
        if not self.minimal:
            dependencies.extend(
                [
                    "google-analytics-data>=0.17.0",
                    "mixpanel>=4.10.0",
                ]
            )
        self.update_pyproject_toml(dependencies)

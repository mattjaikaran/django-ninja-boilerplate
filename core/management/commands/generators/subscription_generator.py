"""Subscription feature generator."""

from .base_generator import BaseGenerator


class SubscriptionGenerator(BaseGenerator):
    """Generator for subscription management feature."""

    def __init__(
        self,
        app_name: str = "subscriptions",
        provider: str = "stripe",
        minimal: bool = False,
    ):
        """Initialize the subscription generator."""
        super().__init__(app_name, minimal)
        self.provider = provider

    def generate(self) -> None:
        """Generate the subscription feature."""
        print(f"Generating subscription feature with {self.provider}...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        print("Subscription feature generated successfully!")
        print("Note: This generator creates a basic structure.")
        print(
            "For full subscription functionality, use: python manage.py generate_feature payments --provider stripe"
        )

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = [f"{self.provider}>=8.0.0"]
        self.update_pyproject_toml(dependencies)

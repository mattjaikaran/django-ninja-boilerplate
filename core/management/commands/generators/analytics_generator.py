"""Analytics feature generator."""

from .base_generator import BaseGenerator, GeneratorError
from .templates.analytics_templates import render_analytics_files


class AnalyticsGenerator(BaseGenerator):
    """Generator for the analytics event tracking feature.

    The app gets an ``Event`` model, a ``JWTAuth`` controller at
    ``/api/analytics/`` where a user tracks and lists their own events, a
    staff-only (``IsAdminUser``) summary of event counts, and one smoke and
    permission test file. It adds no settings and no dependencies.
    """

    def __init__(self, app_name: str = "analytics"):
        """Initialize the analytics generator."""
        super().__init__(app_name)

    def generate(self) -> None:
        """Generate the analytics feature."""
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        self.logger.info("Generating analytics feature in %s...", self.app_name)
        self.create_django_app()
        self.remove_scaffold()
        for relative_path, content in render_analytics_files(self.app_name).items():
            self.create_file(self.app_path / relative_path, content)

        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "AnalyticsController")
        self.create_migration()
        self.logger.info("Analytics feature generated at /api/analytics/")

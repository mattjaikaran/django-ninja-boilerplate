from django.apps import AppConfig


class DecisionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "decisions"
    verbose_name = "Decisions"

    def ready(self) -> None:
        """Register the optional MCP tools when the app starts.

        A no-op unless ``ENABLE_DECISION_MCP`` is true and ``django-ai-boost``
        is installed.
        """
        from decisions.mcp import register

        register()

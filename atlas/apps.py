from django.apps import AppConfig


class AtlasConfig(AppConfig):
    """App config for the Codebase Atlas tool."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "atlas"
    verbose_name = "Codebase Atlas"

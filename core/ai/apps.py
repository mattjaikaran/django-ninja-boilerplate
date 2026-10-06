from django.apps import AppConfig


class AiConfig(AppConfig):
    """Installed only when ``AI_ENABLED`` is true (api/settings/common.py)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core.ai"
    label = "ai"
    verbose_name = "AI and data layer"

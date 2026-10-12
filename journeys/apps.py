from django.apps import AppConfig


class JourneysConfig(AppConfig):
    """App config for the user journeys admin pages."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "journeys"
    verbose_name = "User journeys"

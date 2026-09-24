from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Initialize signal handlers and task registration."""
        from api.tasks.discovery import autodiscover_tasks
        from core.audit.signals import setup_audit_signals

        setup_audit_signals()
        autodiscover_tasks()

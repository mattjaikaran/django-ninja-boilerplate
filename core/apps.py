from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Initialize app when Django starts.

        This method is called when the app is ready.
        Used to set up signal handlers for audit logging.
        """
        # Import and initialize audit signals
        from core.audit.signals import setup_audit_signals

        setup_audit_signals()

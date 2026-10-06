from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Initialize signal handlers, task registration, tracing and Sentry."""
        from api.tasks.discovery import autodiscover_tasks
        from core.audit.signals import setup_audit_signals

        setup_audit_signals()
        autodiscover_tasks()
        self._init_tracing()
        self._init_sentry()

    @staticmethod
    def _init_sentry() -> None:
        """Report errors to Sentry or GlitchTip when ``SENTRY_DSN`` is set."""
        from django.conf import settings

        if not getattr(settings, "SENTRY_DSN", ""):
            return
        from core.observability.sentry import init_sentry

        init_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=settings.VERSION,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        )

    @staticmethod
    def _init_tracing() -> None:
        """Export OpenTelemetry traces when ``OTEL_ENABLED`` is true."""
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        if not getattr(settings, "OTEL_ENABLED", False):
            return
        from core.observability.tracing import init_tracing, instrument_all

        if not init_tracing():
            raise ImproperlyConfigured(
                "OTEL_ENABLED is true but tracing did not start. Install the "
                "`observability` extra (`uv sync --extra observability`) and "
                "check OTEL_EXPORTER_OTLP_ENDPOINT."
            )
        instrument_all()

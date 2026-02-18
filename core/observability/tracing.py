"""OpenTelemetry tracing setup and instrumentation.

This module provides distributed tracing capabilities using OpenTelemetry.
It supports various exporters including OTLP (Jaeger, Tempo) and console output.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer = None
_initialized = False


def init_tracing(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
    enable_console_export: bool = False,
) -> bool:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service for traces. Defaults to OTEL_SERVICE_NAME
            env var or 'django-ninja-app'.
        otlp_endpoint: OTLP exporter endpoint. Defaults to OTEL_EXPORTER_OTLP_ENDPOINT
            env var or 'http://localhost:4317'.
        enable_console_export: If True, also export traces to console (for debugging).

    Returns:
        True if tracing was initialized successfully, False otherwise.
    """
    global _tracer, _initialized

    if _initialized:
        logger.debug("Tracing already initialized")
        return True

    # Check if observability dependencies are installed
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: uv add opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp"
        )
        return False

    try:
        # Get configuration from settings or arguments
        service_name = service_name or getattr(
            settings, "OTEL_SERVICE_NAME", "django-ninja-app"
        )
        otlp_endpoint = otlp_endpoint or getattr(
            settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )

        # Create resource with service name
        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP exporter configured: %s", otlp_endpoint)
        except Exception as e:
            logger.warning("Failed to configure OTLP exporter: %s", e)

        # Optionally add console exporter for debugging
        if enable_console_export or getattr(settings, "OTEL_CONSOLE_EXPORT", False):
            try:
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter

                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
                logger.info("Console span exporter enabled")
            except ImportError:
                pass

        # Set the tracer provider
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)
        _initialized = True

        logger.info(
            "OpenTelemetry tracing initialized for service: %s",
            service_name,
        )
        return True

    except Exception as e:
        logger.exception("Failed to initialize OpenTelemetry tracing: %s", e)
        return False


def get_tracer():
    """Get the global tracer instance.

    Returns:
        OpenTelemetry tracer or a no-op tracer if not initialized.
    """
    global _tracer

    if _tracer is None:
        try:
            from opentelemetry import trace

            _tracer = trace.get_tracer(__name__)
        except ImportError:
            # Return a no-op tracer
            return _NoOpTracer()

    return _tracer


def get_current_trace_id() -> str | None:
    """Get the current trace ID from the active span.

    Returns:
        Trace ID as hex string, or None if no active span.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, "032x")
    except ImportError:
        pass

    return None


def get_current_span_id() -> str | None:
    """Get the current span ID from the active span.

    Returns:
        Span ID as hex string, or None if no active span.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().span_id, "016x")
    except ImportError:
        pass

    return None


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    record_exception: bool = True,
) -> Generator[Any]:
    """Context manager to create a trace span.

    Args:
        name: Name of the span.
        attributes: Optional attributes to add to the span.
        record_exception: If True, record exceptions in the span.

    Yields:
        The created span.

    Example:
        ```python
        with trace_span("process_order", {"order_id": order.id}):
            # Your code here
            process_order(order)
        ```
    """
    tracer = get_tracer()

    try:
        from opentelemetry.trace import Status, StatusCode
    except ImportError:
        # No OpenTelemetry, yield None and continue
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(
                    key,
                    str(value)
                    if not isinstance(value, (int, float, bool, str))
                    else value,
                )

        try:
            yield span
        except Exception as e:
            if record_exception:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


def trace_function(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to trace a function.

    Args:
        name: Optional span name. Defaults to function name.
        attributes: Optional attributes to add to the span.

    Returns:
        Decorated function.

    Example:
        ```python
        @trace_function("process_payment", {"payment_type": "credit_card"})
        def process_payment(amount):
            # Your code here
            pass
        ```
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__name__}"
            with trace_span(span_name, attributes):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_as_current_span(self, name: str, **kwargs):
        """Return a no-op context manager."""
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span context manager."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op attribute setter."""

    def record_exception(self, exception: Exception) -> None:
        """No-op exception recorder."""

    def set_status(self, status: Any) -> None:
        """No-op status setter."""


def instrument_django() -> bool:
    """Instrument Django with OpenTelemetry auto-instrumentation.

    Returns:
        True if instrumentation was successful, False otherwise.
    """
    try:
        from opentelemetry.instrumentation.django import DjangoInstrumentor

        DjangoInstrumentor().instrument()
        logger.info("Django instrumentation enabled")
        return True
    except ImportError:
        logger.warning(
            "Django instrumentation not available. "
            "Install with: uv add opentelemetry-instrumentation-django"
        )
        return False
    except Exception as e:
        logger.warning("Failed to instrument Django: %s", e)
        return False


def instrument_requests() -> bool:
    """Instrument requests library with OpenTelemetry.

    Returns:
        True if instrumentation was successful, False otherwise.
    """
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        logger.info("Requests instrumentation enabled")
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning("Failed to instrument requests: %s", e)
        return False


def instrument_psycopg2() -> bool:
    """Instrument psycopg2 with OpenTelemetry.

    Returns:
        True if instrumentation was successful, False otherwise.
    """
    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

        Psycopg2Instrumentor().instrument()
        logger.info("Psycopg2 instrumentation enabled")
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning("Failed to instrument psycopg2: %s", e)
        return False


def instrument_redis() -> bool:
    """Instrument Redis with OpenTelemetry.

    Returns:
        True if instrumentation was successful, False otherwise.
    """
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning("Failed to instrument Redis: %s", e)
        return False


def instrument_celery() -> bool:
    """Instrument Celery with OpenTelemetry.

    Returns:
        True if instrumentation was successful, False otherwise.
    """
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
        logger.info("Celery instrumentation enabled")
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning("Failed to instrument Celery: %s", e)
        return False


def instrument_all() -> dict[str, bool]:
    """Instrument all supported libraries.

    Returns:
        Dictionary mapping library names to instrumentation success status.
    """
    return {
        "django": instrument_django(),
        "requests": instrument_requests(),
        "psycopg2": instrument_psycopg2(),
        "redis": instrument_redis(),
        "celery": instrument_celery(),
    }

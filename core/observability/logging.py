"""Structured JSON logging configuration.

This module provides structured logging with JSON output, trace context
propagation, and consistent log formatting for production environments.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class StructuredJsonFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs logs in JSON format with consistent field names suitable for
    log aggregation systems like ELK, Loki, or CloudWatch.
    """

    def __init__(
        self,
        include_trace_context: bool = True,
        extra_fields: dict[str, Any] | None = None,
    ):
        """Initialize the formatter.

        Args:
            include_trace_context: If True, include trace_id and span_id in logs.
            extra_fields: Additional fields to include in every log entry.
        """
        super().__init__()
        self.include_trace_context = include_trace_context
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        try:
            import json
        except ImportError:
            return super().format(record)

        # Base log entry
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context if available and enabled
        if self.include_trace_context:
            trace_context = self._get_trace_context()
            if trace_context:
                log_entry.update(trace_context)

        # Add request_id if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        # Add user_id if present
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "message",
                "request_id",
                "user_id",
            ):
                if not key.startswith("_"):
                    log_entry[key] = value

        # Add static extra fields
        log_entry.update(self.extra_fields)

        # Add service name
        log_entry["service"] = getattr(settings, "OTEL_SERVICE_NAME", "django-ninja-app")

        # Add environment
        log_entry["environment"] = getattr(settings, "ENVIRONMENT", "development")

        return json.dumps(log_entry, default=str)

    def _get_trace_context(self) -> dict[str, str] | None:
        """Get trace context from OpenTelemetry."""
        try:
            from .tracing import get_current_span_id, get_current_trace_id

            trace_id = get_current_trace_id()
            span_id = get_current_span_id()

            if trace_id or span_id:
                return {
                    "trace_id": trace_id,
                    "span_id": span_id,
                }
        except ImportError:
            pass

        return None


class TraceContextFilter(logging.Filter):
    """Logging filter that adds trace context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace context to the log record."""
        try:
            from .tracing import get_current_span_id, get_current_trace_id

            record.trace_id = get_current_trace_id() or ""
            record.span_id = get_current_span_id() or ""
        except ImportError:
            record.trace_id = ""
            record.span_id = ""

        return True


class RequestContextFilter(logging.Filter):
    """Logging filter that adds request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request context to the log record."""
        # These will be set by middleware or manually
        if not hasattr(record, "request_id"):
            record.request_id = ""
        if not hasattr(record, "user_id"):
            record.user_id = ""

        return True


def configure_structured_logging(
    level: str = "INFO",
    include_trace_context: bool = True,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get Django LOGGING configuration for structured JSON logging.

    Args:
        level: Default logging level.
        include_trace_context: If True, include trace_id and span_id in logs.
        extra_fields: Additional fields to include in every log entry.

    Returns:
        Django LOGGING configuration dictionary.

    Example:
        ```python
        # In settings.py
        from core.observability.logging import configure_structured_logging

        LOGGING = configure_structured_logging(
            level="INFO",
            include_trace_context=True,
            extra_fields={"app": "my-app"},
        )
        ```
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "trace_context": {
                "()": "core.observability.logging.TraceContextFilter",
            },
            "request_context": {
                "()": "core.observability.logging.RequestContextFilter",
            },
        },
        "formatters": {
            "json": {
                "()": "core.observability.logging.StructuredJsonFormatter",
                "include_trace_context": include_trace_context,
                "extra_fields": extra_fields or {},
            },
            "verbose": {
                "format": "[{asctime}] {levelname} {name} [{trace_id}] {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console_json": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["trace_context", "request_context"],
                "stream": sys.stdout,
            },
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
                "filters": ["trace_context", "request_context"],
            },
        },
        "root": {
            "handlers": ["console_json"],
            "level": level,
        },
        "loggers": {
            "django": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "django.db.backends": {
                "handlers": ["console_json"],
                "level": "WARNING",
                "propagate": False,
            },
            "django.server": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "core": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "api": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "celery": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
            "gunicorn": {
                "handlers": ["console_json"],
                "level": level,
                "propagate": False,
            },
        },
    }


def get_logger(
    name: str,
    extra: dict[str, Any] | None = None,
) -> logging.LoggerAdapter:
    """Get a logger with optional extra context.

    Args:
        name: Logger name (usually __name__).
        extra: Extra context to include in all log messages.

    Returns:
        LoggerAdapter with extra context.

    Example:
        ```python
        from core.observability.logging import get_logger

        logger = get_logger(__name__, {"component": "payment"})
        logger.info("Processing payment", extra={"amount": 100})
        ```
    """
    base_logger = logging.getLogger(name)
    return logging.LoggerAdapter(base_logger, extra or {})


class ContextLogger:
    """Logger that maintains context across log calls.

    Example:
        ```python
        from core.observability.logging import ContextLogger

        logger = ContextLogger(__name__)
        logger.bind(user_id="123", request_id="abc")
        logger.info("User action")  # Includes user_id and request_id
        ```
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> ContextLogger:
        """Bind context to the logger."""
        self._context.update(kwargs)
        return self

    def unbind(self, *keys: str) -> ContextLogger:
        """Remove keys from the context."""
        for key in keys:
            self._context.pop(key, None)
        return self

    def clear(self) -> ContextLogger:
        """Clear all context."""
        self._context.clear()
        return self

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Internal log method that merges context."""
        extra = kwargs.pop("extra", {})
        extra.update(self._context)
        self._logger.log(level, msg, *args, extra=extra, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

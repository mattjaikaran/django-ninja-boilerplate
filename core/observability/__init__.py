"""Observability stack for Django Ninja boilerplate.

This module provides comprehensive observability including:
- OpenTelemetry distributed tracing
- Prometheus metrics collection
- Structured JSON logging
- Observability middleware
- Enhanced health checks
"""

from .health import DetailedHealthChecker
from .logging import configure_structured_logging, get_logger
from .metrics import (
    MetricsRegistry,
    get_metrics_text,
    increment_request_counter,
    observe_request_latency,
    record_error,
)
from .middleware import ObservabilityMiddleware
from .tracing import (
    get_current_trace_id,
    get_tracer,
    init_tracing,
    trace_span,
)

__all__ = [
    # Tracing
    "init_tracing",
    "get_tracer",
    "get_current_trace_id",
    "trace_span",
    # Metrics
    "MetricsRegistry",
    "get_metrics_text",
    "increment_request_counter",
    "observe_request_latency",
    "record_error",
    # Logging
    "configure_structured_logging",
    "get_logger",
    # Middleware
    "ObservabilityMiddleware",
    # Health
    "DetailedHealthChecker",
]

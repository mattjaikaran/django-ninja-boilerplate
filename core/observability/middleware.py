"""Observability middleware for request tracing and metrics.

This middleware provides:
- Automatic trace ID propagation
- Request/response logging with trace context
- Prometheus metrics collection
- Request timing
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

from .metrics import (
    increment_request_counter,
    observe_request_latency,
    record_error,
)
from .tracing import get_current_trace_id, trace_span

logger = logging.getLogger(__name__)


class ObservabilityMiddleware:
    """Middleware for observability: tracing, metrics, and structured logging.

    This middleware:
    1. Creates or propagates trace IDs
    2. Records request metrics (count, latency, errors)
    3. Adds trace context to logs
    4. Adds observability headers to responses
    """

    # Paths to exclude from detailed tracing
    EXCLUDED_PATHS = {
        "/health/",
        "/health/liveness",
        "/health/readiness",
        "/metrics",
        "/favicon.ico",
        "/static/",
        "/media/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request with observability."""
        # Skip excluded paths
        if self._should_skip(request.path):
            return self.get_response(request)

        # Extract or generate trace ID
        trace_id = self._extract_or_generate_trace_id(request)
        request.META["X-Trace-ID"] = trace_id

        # Extract or generate request ID
        request_id = self._extract_or_generate_request_id(request)
        request.META["X-Request-ID"] = request_id

        # Get endpoint for metrics (normalized path)
        endpoint = self._normalize_endpoint(request.path)
        method = request.method

        # Record request start time
        start_time = time.time()

        # Create span attributes
        span_attributes = {
            "http.method": method,
            "http.url": request.build_absolute_uri(),
            "http.target": request.path,
            "http.host": request.get_host(),
            "http.scheme": request.scheme,
            "http.user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }

        # Add user info if authenticated
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            span_attributes["user.id"] = str(request.user.id)

        # Process request within a trace span
        with trace_span(f"{method} {endpoint}", span_attributes) as span:
            try:
                response = self.get_response(request)

                # Record response attributes
                if span:
                    span.set_attribute("http.status_code", response.status_code)

                # Record metrics
                duration = time.time() - start_time
                self._record_metrics(method, endpoint, response.status_code, duration)

                # Add observability headers to response
                response = self._add_response_headers(
                    response, trace_id, request_id, duration
                )

                # Log request completion
                self._log_request(request, response, duration, trace_id, request_id)

                return response

            except Exception as e:
                # Record error metrics
                duration = time.time() - start_time
                record_error(method, endpoint, type(e).__name__)

                # Log error
                logger.exception(
                    "Request failed: %s %s",
                    method,
                    request.path,
                    extra={
                        "trace_id": trace_id,
                        "request_id": request_id,
                        "error": str(e),
                        "duration_ms": round(duration * 1000, 2),
                    },
                )
                raise

    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped from observability."""
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)

    def _extract_or_generate_trace_id(self, request: HttpRequest) -> str:
        """Extract trace ID from headers or generate a new one."""
        # Try W3C Trace Context header first
        traceparent = request.META.get("HTTP_TRACEPARENT")
        if traceparent:
            try:
                # traceparent format: version-trace_id-span_id-flags
                parts = traceparent.split("-")
                if len(parts) >= 2:
                    return parts[1]
            except (IndexError, ValueError):
                pass

        # Try X-Trace-ID header
        trace_id = request.META.get("HTTP_X_TRACE_ID")
        if trace_id:
            return trace_id

        # Try to get from OpenTelemetry
        otel_trace_id = get_current_trace_id()
        if otel_trace_id:
            return otel_trace_id

        # Generate new trace ID
        return uuid.uuid4().hex

    def _extract_or_generate_request_id(self, request: HttpRequest) -> str:
        """Extract request ID from headers or generate a new one."""
        request_id = request.META.get("HTTP_X_REQUEST_ID")
        if request_id:
            return request_id

        return str(uuid.uuid4())[:8]

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize path for metrics (replace IDs with placeholders).

        This prevents high cardinality in metrics labels.
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs
        path = re.sub(r"/\d+(/|$)", "/{id}\\1", path)

        # Remove trailing slash for consistency
        return path.rstrip("/") or "/"

    def _record_metrics(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
    ) -> None:
        """Record request metrics."""
        increment_request_counter(method, endpoint, status_code)
        observe_request_latency(method, endpoint, duration)

        # Record errors separately
        if status_code >= 400:
            error_type = "client_error" if status_code < 500 else "server_error"
            record_error(method, endpoint, error_type)

    def _add_response_headers(
        self,
        response: HttpResponse,
        trace_id: str,
        request_id: str,
        duration: float,
    ) -> HttpResponse:
        """Add observability headers to response."""
        response["X-Trace-ID"] = trace_id
        response["X-Request-ID"] = request_id
        response["X-Response-Time"] = f"{round(duration * 1000, 2)}ms"

        # Add Server-Timing header for browser developer tools
        response["Server-Timing"] = f"total;dur={round(duration * 1000, 2)}"

        return response

    def _log_request(
        self,
        request: HttpRequest,
        response: HttpResponse,
        duration: float,
        trace_id: str,
        request_id: str,
    ) -> None:
        """Log request completion."""
        duration_ms = round(duration * 1000, 2)

        # Determine log level based on status code and duration
        status_code = response.status_code
        slow_threshold_ms = getattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 1000)

        extra = {
            "trace_id": trace_id,
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            "remote_addr": self._get_client_ip(request),
        }

        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            extra["user_id"] = str(request.user.id)

        message = f"{request.method} {request.path} -> {status_code} ({duration_ms}ms)"

        if status_code >= 500:
            logger.error(message, extra=extra)
        elif status_code >= 400:
            logger.warning(message, extra=extra)
        elif duration_ms > slow_threshold_ms:
            logger.warning(f"Slow request: {message}", extra=extra)
        elif settings.DEBUG:
            logger.info(message, extra=extra)
        else:
            logger.debug(message, extra=extra)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class TracingMiddleware:
    """Lightweight middleware for trace ID propagation only.

    Use this instead of ObservabilityMiddleware if you only need
    trace context propagation without metrics.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request with trace ID propagation."""
        # Extract or generate trace ID
        trace_id = request.META.get("HTTP_X_TRACE_ID")
        if not trace_id:
            trace_id = get_current_trace_id() or uuid.uuid4().hex

        request.META["X-Trace-ID"] = trace_id

        response = self.get_response(request)
        response["X-Trace-ID"] = trace_id

        return response

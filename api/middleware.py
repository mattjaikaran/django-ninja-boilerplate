"""Middleware for the Django Ninja Boilerplate API.

This module provides middleware classes for:
- Request/response logging
- Performance monitoring
- Security headers
- Rate limit header injection
"""

import logging
import time
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Middleware for logging API requests and responses.

    Logs request details including:
    - Request ID for tracing
    - HTTP method and path
    - Response status code
    - Request duration
    - User info (if authenticated)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.META["X-Request-ID"] = request_id

        # Record start time
        start_time = time.time()

        # Get response
        response = self.get_response(request)

        # Calculate duration
        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)

        # Only log API requests
        if request.path.startswith("/api/"):
            user_info = "anonymous"
            if (
                hasattr(request, "user")
                and request.user
                and request.user.is_authenticated
            ):
                user_info = f"user:{request.user.id}"

            # Log based on status code
            log_message = (
                f"[{request_id}] {request.method} {request.path} "
                f"-> {response.status_code} ({duration_ms}ms) [{user_info}]"
            )

            if response.status_code >= 500:
                logger.error(log_message)
            elif response.status_code >= 400:
                logger.warning(log_message)
            elif settings.DEBUG or duration_ms > 1000:  # Log slow requests
                logger.info(log_message)
            else:
                logger.debug(log_message)

        # Add headers to response
        response["X-Request-ID"] = request_id
        response["X-Response-Time"] = f"{duration_ms}ms"

        return response


class SecurityHeadersMiddleware:
    """Middleware for adding security headers.

    Adds common security headers to all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Security headers
        if not settings.DEBUG:
            response["X-Content-Type-Options"] = "nosniff"
            response["X-Frame-Options"] = "DENY"
            response["X-XSS-Protection"] = "1; mode=block"
            response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class RateLimitHeaderMiddleware:
    """Middleware for adding rate limit headers to responses.

    Reads rate limit info from request.META and adds headers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add rate limit headers if present
        if hasattr(request, "META"):
            if "X-RateLimit-Limit" in request.META:
                response["X-RateLimit-Limit"] = request.META["X-RateLimit-Limit"]
            if "X-RateLimit-Remaining" in request.META:
                response["X-RateLimit-Remaining"] = request.META[
                    "X-RateLimit-Remaining"
                ]
            if "X-RateLimit-Reset" in request.META:
                response["X-RateLimit-Reset"] = request.META["X-RateLimit-Reset"]

        return response


class PerformanceMonitoringMiddleware:
    """Middleware for performance monitoring.

    Tracks slow requests and logs performance metrics.
    """

    # Threshold for slow requests in seconds
    SLOW_REQUEST_THRESHOLD = 1.0

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        start_queries = self._get_query_count()

        response = self.get_response(request)

        duration = time.time() - start_time
        end_queries = self._get_query_count()
        query_count = end_queries - start_queries

        # Log slow requests
        if duration > self.SLOW_REQUEST_THRESHOLD:
            logger.warning(
                "Slow request: %s %s took %.2fs with %d queries",
                request.method,
                request.path,
                duration,
                query_count,
            )

        # Log requests with many queries (N+1 detection)
        if query_count > 20:
            logger.warning(
                "High query count: %s %s made %d queries",
                request.method,
                request.path,
                query_count,
            )

        # Add debug info in development
        if settings.DEBUG:
            response["X-DB-Queries"] = str(query_count)

        return response

    def _get_query_count(self):
        """Get current query count from Django debug toolbar or connection."""
        try:
            from django.db import connection

            return len(connection.queries)
        except Exception:
            return 0

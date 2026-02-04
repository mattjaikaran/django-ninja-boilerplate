"""Audit Logging Middleware.

This middleware logs API requests and responses for compliance tracking.
It captures request metadata, response status, and timing information.
"""

import logging
import time
import uuid
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> str | None:
    """Extract the client IP address from the request.

    Handles proxy headers (X-Forwarded-For) for load-balanced environments.

    Args:
        request: The HTTP request object

    Returns:
        Client IP address or None
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain (client IP)
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


class AuditLoggingMiddleware:
    """Middleware for logging API requests and responses.

    This middleware:
    - Assigns a unique request ID to each request
    - Logs request metadata (method, path, IP, user agent)
    - Logs response status and timing
    - Stores audit logs for API endpoints

    Configuration via settings:
    - AUDIT_LOG_ENABLED: Enable/disable audit logging (default: True)
    - AUDIT_LOG_PATHS: List of path prefixes to audit (default: ["/api/"])
    - AUDIT_LOG_EXCLUDE_PATHS: Paths to exclude (default: ["/api/health/", "/api/docs"])
    - AUDIT_LOG_BODY: Log request/response bodies (default: False, for privacy)
    - AUDIT_LOG_MAX_BODY_LENGTH: Max body length to log (default: 1000)
    """

    def __init__(self, get_response):
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain
        """
        self.get_response = get_response

        # Configuration from settings with defaults
        self.enabled = getattr(settings, "AUDIT_LOG_ENABLED", True)
        self.audit_paths = getattr(settings, "AUDIT_LOG_PATHS", ["/api/"])
        self.exclude_paths = getattr(
            settings,
            "AUDIT_LOG_EXCLUDE_PATHS",
            ["/api/health/", "/api/docs", "/api/openapi.json"],
        )
        self.log_body = getattr(settings, "AUDIT_LOG_BODY", False)
        self.max_body_length = getattr(settings, "AUDIT_LOG_MAX_BODY_LENGTH", 1000)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and response.

        Args:
            request: The HTTP request object

        Returns:
            The HTTP response object
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.audit_request_id = request_id

        # Check if we should audit this request
        should_audit = self._should_audit(request)

        if should_audit:
            # Capture request start time
            start_time = time.time()

            # Store request metadata for later
            request.audit_metadata = self._capture_request_metadata(request)

        # Process the request
        response = self.get_response(request)

        if should_audit:
            # Calculate request duration
            duration = time.time() - start_time

            # Log the request/response
            self._log_request(request, response, duration)

        # Add request ID to response headers for debugging
        response["X-Request-ID"] = request_id

        return response

    def _should_audit(self, request: HttpRequest) -> bool:
        """Determine if this request should be audited.

        Args:
            request: The HTTP request object

        Returns:
            True if the request should be audited
        """
        if not self.enabled:
            return False

        path = request.path

        # Check exclusions first
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return False

        # Check if path matches audit paths
        return any(path.startswith(audit_path) for audit_path in self.audit_paths)

    def _capture_request_metadata(self, request: HttpRequest) -> dict[str, Any]:
        """Capture metadata from the request.

        Args:
            request: The HTTP request object

        Returns:
            Dictionary of request metadata
        """
        metadata = {
            "method": request.method,
            "path": request.path,
            "query_string": request.META.get("QUERY_STRING", ""),
            "ip_address": get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "content_type": request.content_type,
        }

        # Optionally capture request body (be careful with sensitive data)
        if self.log_body and request.body:
            try:
                body = request.body.decode("utf-8")
                if len(body) > self.max_body_length:
                    body = body[: self.max_body_length] + "... [truncated]"
                # Mask sensitive fields
                metadata["request_body"] = self._mask_sensitive_data(body)
            except UnicodeDecodeError:
                metadata["request_body"] = "[binary data]"

        return metadata

    def _mask_sensitive_data(self, data: str) -> str:
        """Mask sensitive data in request/response bodies.

        Args:
            data: The data string to mask

        Returns:
            Masked data string
        """
        sensitive_patterns = [
            "password",
            "token",
            "secret",
            "api_key",
            "apikey",
            "authorization",
            "credit_card",
            "cvv",
            "ssn",
        ]

        masked_data = data
        for pattern in sensitive_patterns:
            # Simple masking - in production, use regex for better accuracy
            if pattern.lower() in masked_data.lower():
                # This is a simple approach; consider using regex for JSON
                masked_data = masked_data.replace(
                    f'"{pattern}":', f'"{pattern}": "[REDACTED]",'
                )

        return masked_data

    def _log_request(
        self,
        request: HttpRequest,
        response: HttpResponse,
        duration: float,
    ) -> None:
        """Log the request and response to the audit log.

        Args:
            request: The HTTP request object
            response: The HTTP response object
            duration: Request duration in seconds
        """
        # Import here to avoid circular imports
        from core.audit.models import AuditAction, AuditLog

        metadata = getattr(request, "audit_metadata", {})
        request_id = getattr(request, "audit_request_id", "")

        # Get the current user
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

        # Determine success based on status code
        success = response.status_code < 400

        # Build extra data
        extra_data = {
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "query_string": metadata.get("query_string", ""),
            "content_type": metadata.get("content_type", ""),
        }

        if self.log_body and metadata.get("request_body"):
            extra_data["request_body"] = metadata["request_body"]

        # Create audit log entry
        try:
            AuditLog.log_action(
                action=AuditAction.API_REQUEST,
                action_description=f"{metadata.get('method', 'UNKNOWN')} {metadata.get('path', 'unknown')}",
                user=user,
                ip_address=metadata.get("ip_address"),
                user_agent=metadata.get("user_agent", ""),
                request_method=metadata.get("method", ""),
                request_path=metadata.get("path", ""),
                request_id=request_id,
                extra_data=extra_data,
                success=success,
                error_message="" if success else f"HTTP {response.status_code}",
            )
        except Exception as e:
            # Don't let audit logging failures break the request
            logger.exception("Failed to create audit log entry: %s", e)


# Export the get_client_ip function for use in other modules
__all__ = ["AuditLoggingMiddleware", "get_client_ip"]

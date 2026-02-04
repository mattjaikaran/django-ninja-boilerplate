"""Observability API controllers for metrics and enhanced health checks.

This module provides API endpoints for:
- Prometheus metrics scraping
- Enhanced health checks with detailed status
"""

from __future__ import annotations

import logging

from django.http import HttpResponse
from ninja_extra import api_controller, http_get

from .health import get_health_checker, run_health_checks
from .metrics import get_metrics_text, set_app_info

logger = logging.getLogger(__name__)


@api_controller("/metrics", tags=["Observability"])
class MetricsController:
    """Prometheus metrics endpoint for scraping."""

    @http_get(
        "",
        response={200: None},
        summary="Prometheus Metrics",
        description="Returns metrics in Prometheus exposition format for scraping.",
        include_in_schema=False,  # Hide from OpenAPI docs
    )
    def get_metrics(self, request) -> HttpResponse:
        """Return Prometheus metrics in text format.

        This endpoint is designed for Prometheus scraping and returns
        metrics in the Prometheus exposition format.
        """
        # Set app info gauge
        set_app_info()

        # Get metrics text
        metrics_text = get_metrics_text()

        return HttpResponse(
            metrics_text,
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )


@api_controller("/health", tags=["Health"])
class EnhancedHealthController:
    """Enhanced health check endpoints with detailed status."""

    @http_get("/detailed", response={200: dict})
    def detailed_health(self, request) -> tuple[int, dict]:
        """Get detailed health status of all components.

        Returns comprehensive health information including:
        - Database connectivity
        - Cache (Redis) availability
        - Custom registered health checks
        - Response times for each check
        """
        result = run_health_checks()
        return 200, result.to_dict()

    @http_get("/component/{component}", response={200: dict})
    def component_health(self, request, component: str) -> tuple[int, dict]:
        """Get health status of a specific component.

        Args:
            request: The HTTP request object.
            component: Name of the component to check (e.g., 'database', 'cache', 'redis').
        """
        health_checker = get_health_checker()
        result = health_checker.run_check(component)

        status_code = 200 if result.status.value in ("healthy", "degraded") else 503

        return status_code, {
            "name": result.name,
            "status": result.status.value,
            "message": result.message,
            "response_time_ms": result.response_time_ms,
            "details": result.details,
            "timestamp": result.timestamp.isoformat(),
        }

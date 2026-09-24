"""Observability API controllers for metrics.

Health endpoints live in ``api.healthcheck`` (the single health controller).
The former ``EnhancedHealthController`` was removed so that exactly one
controller owns the ``/health`` prefix, keeping runtime routing and the
OpenAPI schema in agreement.
"""

from __future__ import annotations

import logging

from django.http import HttpResponse
from ninja_extra import api_controller, http_get
from ninja_jwt.authentication import JWTAuth

from .metrics import get_metrics_text, set_app_info

logger = logging.getLogger(__name__)


def _is_staff(request) -> bool:
    """Return True when the request user is an authenticated staff member."""
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


@api_controller("/metrics", tags=["Observability"])
class MetricsController:
    """Prometheus metrics endpoint for scraping (staff only)."""

    @http_get(
        "",
        response={200: None, 403: dict},
        summary="Prometheus Metrics",
        description="Returns metrics in Prometheus exposition format for scraping.",
        include_in_schema=False,  # Hide from OpenAPI docs
        auth=JWTAuth(),
    )
    def get_metrics(self, request) -> HttpResponse | tuple[int, dict]:
        """Return Prometheus metrics in text format (staff only)."""
        if not _is_staff(request):
            return 403, {"detail": "Staff credentials required"}

        # Set app info gauge
        set_app_info()

        # Get metrics text
        metrics_text = get_metrics_text()

        return HttpResponse(
            metrics_text,
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )

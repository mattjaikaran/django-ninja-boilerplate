"""Health check endpoints for liveness, readiness, and detailed status.

Endpoints (mounted at /api/health by the API router):

    GET /health/                    — public, no I/O (liveness-style)
    GET /health/liveness            — public, probes nothing
    GET /health/readiness           — public, checks database + cache only
    GET /health/detailed            — staff JWT, full component checks
    GET /health/component/{name}    — staff JWT, single component check
    GET /health/system              — staff JWT, host resource stats
"""

import logging
from datetime import UTC, datetime

from django.conf import settings
from ninja_extra import api_controller, http_get
from core.security.cookie_auth import CookieJWTAuth

from core.monitoring.performance import system_stats
from core.observability.health import (
    HealthStatus,
    get_health_checker,
    run_health_checks,
)

logger = logging.getLogger(__name__)

# Traffic-required dependencies checked by the readiness probe. These are the
# only components that must be up for the instance to serve traffic; optional
# or slow checks (redis, celery, external services) are deliberately excluded.
READINESS_CHECKS = ("database", "cache")


def _now() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def _is_staff(request) -> bool:
    """Return True when the request user is an authenticated staff member."""
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


@api_controller("/health", tags=["Health"], use_unique_op_id=False)
class HealthCheckController:
    """Health check endpoints for system monitoring."""

    @http_get("/", response={200: dict})
    def basic_health_check(self, request):
        """Public liveness-style check. Performs no I/O."""
        return 200, {
            "status": "healthy",
            "timestamp": _now(),
            "version": getattr(settings, "VERSION", "unknown"),
        }

    @http_get("/liveness", response={200: dict})
    def liveness_check(self, request):
        """Kubernetes liveness probe. Probes nothing."""
        return 200, {"alive": True, "timestamp": _now()}

    @http_get("/readiness", response={200: dict, 503: dict})
    def readiness_check(self, request):
        """Kubernetes readiness probe.

        Checks only the traffic-required dependencies (database and cache) and
        returns 503 when either is unavailable.
        """
        result = get_health_checker().run_checks(list(READINESS_CHECKS))
        ready = result.status == HealthStatus.HEALTHY
        status_code = 200 if ready else 503
        return status_code, {
            "ready": ready,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "checks": {check.name: check.status.value for check in result.checks},
        }

    @http_get(
        "/detailed",
        response={200: dict, 403: dict, 503: dict},
        auth=CookieJWTAuth(),
    )
    def detailed_health_check(self, request):
        """Staff-only detailed health check across all components."""
        if not _is_staff(request):
            return 403, {"detail": "Staff credentials required"}

        result = run_health_checks()
        status_code = (
            200
            if result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            else 503
        )
        return status_code, result.to_dict()

    @http_get(
        "/component/{component}",
        response={200: dict, 403: dict, 503: dict},
        auth=CookieJWTAuth(),
    )
    def component_health(self, request, component: str):
        """Staff-only health check for a single named component."""
        if not _is_staff(request):
            return 403, {"detail": "Staff credentials required"}

        result = get_health_checker().run_check(component)
        status_code = (
            200
            if result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            else 503
        )
        return status_code, {
            "name": result.name,
            "status": result.status.value,
            "message": result.message,
            "response_time_ms": result.response_time_ms,
            "details": result.details,
            "timestamp": result.timestamp.isoformat(),
        }

    @http_get("/system", response={200: dict, 403: dict}, auth=CookieJWTAuth())
    def system_health_check(self, request):
        """Staff-only host resource usage check."""
        if not _is_staff(request):
            return 403, {"detail": "Staff credentials required"}

        try:
            stats = system_stats()

            status = "healthy"
            warnings = []

            if stats.get("memory", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High memory usage")

            if stats.get("cpu", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High CPU usage")

            if stats.get("disk", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High disk usage")

            return 200, {
                "status": status,
                "warnings": warnings,
                "timestamp": _now(),
                "system_stats": stats,
            }
        except Exception as e:
            logger.error("System health check failed: %s", e)
            return 200, {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": _now(),
            }

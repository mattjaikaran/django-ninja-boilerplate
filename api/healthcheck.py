"""Health check endpoints for monitoring system status."""

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from ninja_extra import api_controller, http_get

from core.monitoring.performance import system_stats

logger = logging.getLogger(__name__)


@api_controller("/health", tags=["Health"])
class HealthCheckController:
    """Health check endpoints for system monitoring."""

    @http_get("/", response={200: dict})
    def basic_health_check(self, request):
        """Basic health check endpoint."""
        return 200, {
            "status": "healthy",
            "timestamp": self._get_timestamp(),
            "version": getattr(settings, "VERSION", "unknown"),
        }

    @http_get("/detailed", response={200: dict})
    def detailed_health_check(self, request):
        """Detailed health check with database and cache status."""
        health_data = {
            "status": "healthy",
            "timestamp": self._get_timestamp(),
            "version": getattr(settings, "VERSION", "unknown"),
            "checks": {},
        }

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_data["checks"]["database"] = {"status": "healthy"}
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            health_data["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_data["status"] = "unhealthy"

        # Cache check
        try:
            test_key = "health_check_test"
            cache.set(test_key, "test_value", 30)
            cached_value = cache.get(test_key)
            if cached_value == "test_value":
                health_data["checks"]["cache"] = {"status": "healthy"}
                cache.delete(test_key)
            else:
                health_data["checks"]["cache"] = {
                    "status": "unhealthy",
                    "error": "Cache test failed",
                }
                health_data["status"] = "unhealthy"
        except Exception as e:
            logger.error("Cache health check failed: %s", e)
            health_data["checks"]["cache"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_data["status"] = "unhealthy"

        # Email service check (if configured)
        health_data["checks"]["email"] = self._check_email_service()

        return 200, health_data

    @http_get("/system", response={200: dict})
    def system_health_check(self, request):
        """System performance and resource usage check."""
        try:
            stats = system_stats()

            # Determine health based on resource usage
            status = "healthy"
            warnings = []

            # Check memory usage
            if stats.get("memory", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High memory usage")

            # Check CPU usage
            if stats.get("cpu", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High CPU usage")

            # Check disk usage
            if stats.get("disk", {}).get("percent", 0) > 90:
                status = "degraded"
                warnings.append("High disk usage")

            return 200, {
                "status": status,
                "warnings": warnings,
                "timestamp": self._get_timestamp(),
                "system_stats": stats,
            }
        except Exception as e:
            logger.error("System health check failed: %s", e)
            return 200, {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": self._get_timestamp(),
            }

    @http_get("/readiness", response={200: dict})
    def readiness_check(self, request):
        """Kubernetes readiness probe endpoint."""
        checks = {}
        ready = True

        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = True
        except Exception:
            checks["database"] = False
            ready = False

        # Check cache
        try:
            cache.get("test")
            checks["cache"] = True
        except Exception:
            checks["cache"] = False
            ready = False

        return 200, {
            "ready": ready,
            "checks": checks,
            "timestamp": self._get_timestamp(),
        }

    @http_get("/liveness", response={200: dict})
    def liveness_check(self, request):
        """Kubernetes liveness probe endpoint."""
        return 200, {
            "alive": True,
            "timestamp": self._get_timestamp(),
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()

    def _check_email_service(self) -> dict[str, Any]:
        """Check email service health."""
        try:
            from django.core.mail import get_connection

            connection = get_connection()
            connection.open()
            connection.close()

            return {"status": "healthy"}
        except Exception as e:
            logger.warning("Email service check failed: %s", e)
            return {
                "status": "degraded",
                "error": "Email service not available",
            }

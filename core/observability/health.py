"""Enhanced health checks with detailed status.

This module provides comprehensive health checking capabilities for:
- Database connectivity
- Cache (Redis) availability
- External service dependencies
- Custom health checks
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str | None = None
    response_time_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class OverallHealthResult:
    """Overall health status aggregating all checks."""

    status: HealthStatus
    checks: list[HealthCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str | None = None
    environment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "environment": self.environment,
            "checks": {
                check.name: {
                    "status": check.status.value,
                    "message": check.message,
                    "response_time_ms": check.response_time_ms,
                    "details": check.details,
                }
                for check in self.checks
            },
        }


class DetailedHealthChecker:
    """Comprehensive health checker with multiple check types."""

    def __init__(self):
        self._checks: dict[str, Callable[[], HealthCheckResult]] = {}
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check("database", self._check_database)
        self.register_check("cache", self._check_cache)
        self.register_check("redis", self._check_redis)

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], HealthCheckResult],
    ) -> None:
        """Register a health check.

        Args:
            name: Name of the health check.
            check_fn: Function that performs the check and returns HealthCheckResult.
        """
        self._checks[name] = check_fn

    def unregister_check(self, name: str) -> None:
        """Unregister a health check."""
        self._checks.pop(name, None)

    def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check.

        Args:
            name: Name of the health check to run.

        Returns:
            HealthCheckResult for the check.
        """
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Unknown health check: {name}",
            )

        start_time = time.time()
        try:
            result = self._checks[name]()
            result.response_time_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    def run_all_checks(self) -> OverallHealthResult:
        """Run all registered health checks.

        Returns:
            OverallHealthResult with aggregated status.
        """
        results = [self.run_check(name) for name in self._checks]

        # Determine overall status
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall_status = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            overall_status = HealthStatus.DEGRADED
        elif all(r.status == HealthStatus.HEALTHY for r in results):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        return OverallHealthResult(
            status=overall_status,
            checks=results,
            version=getattr(settings, "VERSION", "unknown"),
            environment=getattr(settings, "ENVIRONMENT", "unknown"),
        )

    def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                details={
                    "vendor": connection.vendor,
                    "alias": connection.alias,
                },
            )
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e}",
            )

    def _check_cache(self) -> HealthCheckResult:
        """Check cache connectivity."""
        try:
            from django.core.cache import cache

            test_key = "_health_check_test"
            test_value = "health_check"

            cache.set(test_key, test_value, timeout=30)
            cached_value = cache.get(test_key)
            cache.delete(test_key)

            if cached_value == test_value:
                return HealthCheckResult(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    message="Cache operations successful",
                )
            return HealthCheckResult(
                name="cache",
                status=HealthStatus.DEGRADED,
                message="Cache read/write mismatch",
            )

        except Exception as e:
            logger.error("Cache health check failed: %s", e)
            return HealthCheckResult(
                name="cache",
                status=HealthStatus.UNHEALTHY,
                message=f"Cache connection failed: {e}",
            )

    def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity directly."""
        try:
            import redis

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(redis_url)
            info = client.info()

            return HealthCheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                details={
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                },
            )
        except ImportError:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNKNOWN,
                message="Redis client not installed",
            )
        except Exception as e:
            logger.error("Redis health check failed: %s", e)
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {e}",
            )


def check_celery() -> HealthCheckResult:
    """Check Celery worker availability."""
    try:
        from api.celery import app

        inspector = app.control.inspect()
        active_workers = inspector.active()

        if active_workers:
            worker_count = len(active_workers)
            return HealthCheckResult(
                name="celery",
                status=HealthStatus.HEALTHY,
                message=f"{worker_count} worker(s) available",
                details={
                    "workers": list(active_workers.keys()),
                },
            )
        return HealthCheckResult(
            name="celery",
            status=HealthStatus.DEGRADED,
            message="No active Celery workers",
        )

    except Exception as e:
        logger.error("Celery health check failed: %s", e)
        return HealthCheckResult(
            name="celery",
            status=HealthStatus.UNHEALTHY,
            message=f"Celery check failed: {e}",
        )


def check_external_service(
    name: str,
    url: str,
    timeout: float = 5.0,
) -> HealthCheckResult:
    """Check an external HTTP service.

    Args:
        name: Name of the service.
        url: URL to check (should return 2xx status).
        timeout: Request timeout in seconds.

    Returns:
        HealthCheckResult for the service.
    """
    try:
        import httpx

        response = httpx.get(url, timeout=timeout, follow_redirects=True)

        if response.is_success:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.HEALTHY,
                message=f"Service responding (HTTP {response.status_code})",
                details={"status_code": response.status_code},
            )
        return HealthCheckResult(
            name=name,
            status=HealthStatus.DEGRADED,
            message=f"Service returned HTTP {response.status_code}",
            details={"status_code": response.status_code},
        )

    except Exception as e:
        logger.error("External service health check failed for %s: %s", name, e)
        return HealthCheckResult(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=f"Service unreachable: {e}",
        )


# Global health checker instance
_health_checker: DetailedHealthChecker | None = None


def get_health_checker() -> DetailedHealthChecker:
    """Get the global health checker instance."""
    global _health_checker

    if _health_checker is None:
        _health_checker = DetailedHealthChecker()

    return _health_checker


def register_health_check(
    name: str,
    check_fn: Callable[[], HealthCheckResult],
) -> None:
    """Register a health check with the global checker.

    Args:
        name: Name of the health check.
        check_fn: Function that performs the check.

    Example:
        ```python
        from core.observability.health import register_health_check, HealthCheckResult, HealthStatus

        def check_payment_provider():
            # Check payment provider availability
            return HealthCheckResult(
                name="payment_provider",
                status=HealthStatus.HEALTHY,
                message="Payment provider available",
            )

        register_health_check("payment_provider", check_payment_provider)
        ```
    """
    get_health_checker().register_check(name, check_fn)


def run_health_checks() -> OverallHealthResult:
    """Run all health checks.

    Returns:
        OverallHealthResult with aggregated status.
    """
    return get_health_checker().run_all_checks()

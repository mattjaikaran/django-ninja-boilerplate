"""Metrics collection and monitoring utilities."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class ApiMetric:
    """API request metric data."""

    endpoint: str
    method: str
    status_code: int
    response_time: float
    timestamp: float
    user_id: str | None = None
    error_message: str | None = None


@dataclass
class MetricsCollector:
    """Collects and stores application metrics."""

    metrics: dict[str, list] = field(default_factory=lambda: defaultdict(list))

    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        user_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record an API request metric."""
        metric = ApiMetric(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            timestamp=time.time(),
            user_id=user_id,
            error_message=error_message,
        )

        self.metrics["api_requests"].append(metric)

        # Also store in cache for quick access
        cache_key = f"metrics:api_requests:{endpoint}:{method}"
        cached_metrics = cache.get(cache_key, [])
        cached_metrics.append(metric)

        # Keep only recent metrics (last 1000)
        if len(cached_metrics) > 1000:
            cached_metrics = cached_metrics[-1000:]

        cache.set(cache_key, cached_metrics, 3600)  # 1 hour

    def record_database_query(
        self,
        query_type: str,
        table: str,
        duration: float,
        query_count: int = 1,
    ) -> None:
        """Record database query metrics."""
        metric = {
            "query_type": query_type,
            "table": table,
            "duration": duration,
            "query_count": query_count,
            "timestamp": time.time(),
        }

        self.metrics["database_queries"].append(metric)

    def record_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record error metrics."""
        metric = {
            "error_type": error_type,
            "error_message": error_message,
            "endpoint": endpoint,
            "user_id": user_id,
            "timestamp": time.time(),
        }

        self.metrics["errors"].append(metric)

        # Log the error
        logger.error(
            "Error recorded: %s - %s (Endpoint: %s, User: %s)",
            error_type,
            error_message,
            endpoint,
            user_id,
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of collected metrics."""
        summary = {}

        # API request metrics
        api_requests = self.metrics.get("api_requests", [])
        if api_requests:
            total_requests = len(api_requests)
            avg_response_time = (
                sum(m.response_time for m in api_requests) / total_requests
            )
            error_rate = (
                sum(1 for m in api_requests if m.status_code >= 400) / total_requests
            )

            summary["api_requests"] = {
                "total": total_requests,
                "avg_response_time": avg_response_time,
                "error_rate": error_rate,
            }

        # Database query metrics
        db_queries = self.metrics.get("database_queries", [])
        if db_queries:
            total_queries = sum(m["query_count"] for m in db_queries)
            avg_query_time = sum(m["duration"] for m in db_queries) / len(db_queries)

            summary["database_queries"] = {
                "total": total_queries,
                "avg_duration": avg_query_time,
            }

        # Error metrics
        errors = self.metrics.get("errors", [])
        if errors:
            summary["errors"] = {
                "total": len(errors),
                "by_type": defaultdict(int),
            }
            for error in errors:
                summary["errors"]["by_type"][error["error_type"]] += 1

        return summary


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def record_api_request(
    endpoint: str,
    method: str,
    status_code: int,
    response_time: float,
    user_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Record an API request metric."""
    _metrics_collector.record_api_request(
        endpoint, method, status_code, response_time, user_id, error_message
    )


def record_database_query(
    query_type: str,
    table: str,
    duration: float,
    query_count: int = 1,
) -> None:
    """Record database query metrics."""
    _metrics_collector.record_database_query(query_type, table, duration, query_count)


def record_error_metric(
    error_type: str,
    error_message: str,
    endpoint: str | None = None,
    user_id: str | None = None,
) -> None:
    """Record error metrics."""
    _metrics_collector.record_error(error_type, error_message, endpoint, user_id)


def record_response_time(endpoint: str, method: str, response_time: float) -> None:
    """Record API response time."""
    cache_key = f"metrics:response_times:{endpoint}:{method}"
    times = cache.get(cache_key, [])
    times.append(response_time)

    # Keep only recent times (last 100)
    if len(times) > 100:
        times = times[-100:]

    cache.set(cache_key, times, 1800)  # 30 minutes


def get_metrics_summary() -> dict[str, Any]:
    """Get metrics summary."""
    return _metrics_collector.get_metrics_summary()

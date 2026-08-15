"""Prometheus metrics collection and exposition.

This module provides Prometheus-compatible metrics for monitoring
request counts, latency, error rates, and custom business metrics.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Global metrics registry
_metrics_registry = None
_registry_lock = Lock()


@dataclass
class HistogramBucket:
    """Histogram bucket for latency measurements."""

    le: float  # less than or equal
    count: int = 0


@dataclass
class MetricValue:
    """Container for metric values with labels."""

    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Counter:
    """Prometheus-style counter metric."""

    def __init__(
        self, name: str, description: str, label_names: list[str] | None = None
    ):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the counter."""
        label_key = self._make_label_key(labels)
        with self._lock:
            self._values[label_key] += value

    def _make_label_key(self, labels: dict[str, str] | None) -> tuple:
        """Create a hashable key from labels."""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def get_samples(self) -> list[tuple[dict[str, str], float]]:
        """Get all metric samples."""
        samples = []
        with self._lock:
            for label_key, value in self._values.items():
                labels = dict(label_key) if label_key else {}
                samples.append((labels, value))
        return samples


class Gauge:
    """Prometheus-style gauge metric."""

    def __init__(
        self, name: str, description: str, label_names: list[str] | None = None
    ):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge value."""
        label_key = self._make_label_key(labels)
        with self._lock:
            self._values[label_key] = value

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge."""
        label_key = self._make_label_key(labels)
        with self._lock:
            self._values[label_key] += value

    def dec(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge."""
        label_key = self._make_label_key(labels)
        with self._lock:
            self._values[label_key] -= value

    def _make_label_key(self, labels: dict[str, str] | None) -> tuple:
        """Create a hashable key from labels."""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def get_samples(self) -> list[tuple[dict[str, str], float]]:
        """Get all metric samples."""
        samples = []
        with self._lock:
            for label_key, value in self._values.items():
                labels = dict(label_key) if label_key else {}
                samples.append((labels, value))
        return samples


class Histogram:
    """Prometheus-style histogram metric."""

    # Default buckets for HTTP request latencies (in seconds)
    DEFAULT_BUCKETS = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        float("inf"),
    )

    def __init__(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._bucket_counts: dict[tuple, dict[float, int]] = defaultdict(
            lambda: dict.fromkeys(self.buckets, 0)
        )
        self._sums: dict[tuple, float] = defaultdict(float)
        self._counts: dict[tuple, int] = defaultdict(int)
        self._lock = Lock()

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a value."""
        label_key = self._make_label_key(labels)
        with self._lock:
            self._sums[label_key] += value
            self._counts[label_key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[label_key][bucket] += 1

    def _make_label_key(self, labels: dict[str, str] | None) -> tuple:
        """Create a hashable key from labels."""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def get_samples(self) -> list[tuple[str, dict[str, str], float]]:
        """Get all metric samples including buckets, sum, and count."""
        samples = []
        with self._lock:
            for label_key in set(self._bucket_counts.keys()) | set(self._sums.keys()):
                labels = dict(label_key) if label_key else {}

                # Bucket samples
                cumulative: float = 0.0
                for bucket in self.buckets:
                    cumulative += self._bucket_counts[label_key].get(bucket, 0)
                    bucket_labels = {
                        **labels,
                        "le": str(bucket) if bucket != float("inf") else "+Inf",
                    }
                    samples.append((f"{self.name}_bucket", bucket_labels, cumulative))

                # Sum and count
                samples.append((f"{self.name}_sum", labels, self._sums[label_key]))
                samples.append((f"{self.name}_count", labels, self._counts[label_key]))

        return samples


class MetricsRegistry:
    """Registry for all application metrics."""

    def __init__(self):
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = Lock()

        # Initialize default metrics
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """Initialize default application metrics."""
        # HTTP request metrics
        self.register_counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        self.register_histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
        )

        self.register_counter(
            "http_request_errors_total",
            "Total HTTP request errors",
            ["method", "endpoint", "error_type"],
        )

        # Database metrics
        self.register_counter(
            "db_queries_total",
            "Total database queries",
            ["operation", "table"],
        )

        self.register_histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["operation"],
        )

        # Application metrics
        self.register_gauge(
            "app_info",
            "Application information",
            ["version", "environment"],
        )

        self.register_gauge(
            "active_users",
            "Number of active users",
            [],
        )

        # Cache metrics
        self.register_counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_name"],
        )

        self.register_counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_name"],
        )

    def register_counter(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
    ) -> Counter:
        """Register a counter metric."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description, label_names)
            return self._counters[name]

    def register_gauge(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
    ) -> Gauge:
        """Register a gauge metric."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description, label_names)
            return self._gauges[name]

    def register_histogram(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> Histogram:
        """Register a histogram metric."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(
                    name, description, label_names, buckets
                )
            return self._histograms[name]

    def get_counter(self, name: str) -> Counter | None:
        """Get a counter by name."""
        return self._counters.get(name)

    def get_gauge(self, name: str) -> Gauge | None:
        """Get a gauge by name."""
        return self._gauges.get(name)

    def get_histogram(self, name: str) -> Histogram | None:
        """Get a histogram by name."""
        return self._histograms.get(name)

    def generate_prometheus_text(self) -> str:
        """Generate Prometheus exposition format text."""
        lines = []

        # Counters
        for name, counter in self._counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            for labels, value in counter.get_samples():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Gauges
        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {name} {gauge.description}")
            lines.append(f"# TYPE {name} gauge")
            for labels, value in gauge.get_samples():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Histograms
        for name, histogram in self._histograms.items():
            lines.append(f"# HELP {name} {histogram.description}")
            lines.append(f"# TYPE {name} histogram")
            for metric_name, labels, value in histogram.get_samples():
                label_str = self._format_labels(labels)
                lines.append(f"{metric_name}{label_str} {value}")

        return "\n".join(lines) + "\n"

    def snapshot(self) -> dict[str, Any]:
        """Collect all registered metrics for display.

        Returns one list per metric type; each entry carries the name,
        description, and raw samples so callers can render them without
        reaching into the registry internals.
        """
        return {
            "counters": [
                {
                    "name": name,
                    "description": counter.description,
                    "samples": counter.get_samples(),
                }
                for name, counter in self._counters.items()
            ],
            "gauges": [
                {
                    "name": name,
                    "description": gauge.description,
                    "samples": gauge.get_samples(),
                }
                for name, gauge in self._gauges.items()
            ],
            "histograms": [
                {
                    "name": name,
                    "description": histogram.description,
                    "samples": histogram.get_samples(),
                }
                for name, histogram in self._histograms.items()
            ],
        }

    def _format_labels(self, labels: dict[str, str]) -> str:
        """Format labels for Prometheus exposition."""
        if not labels:
            return ""
        label_parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_parts) + "}"


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _metrics_registry

    with _registry_lock:
        if _metrics_registry is None:
            _metrics_registry = MetricsRegistry()
        return _metrics_registry


def get_metrics_text() -> str:
    """Get metrics in Prometheus exposition format."""
    return get_metrics_registry().generate_prometheus_text()


def increment_request_counter(
    method: str,
    endpoint: str,
    status: int,
) -> None:
    """Increment the HTTP request counter."""
    registry = get_metrics_registry()
    counter = registry.get_counter("http_requests_total")
    if counter:
        counter.inc(
            labels={"method": method, "endpoint": endpoint, "status": str(status)}
        )


def observe_request_latency(
    method: str,
    endpoint: str,
    duration: float,
) -> None:
    """Observe HTTP request latency."""
    registry = get_metrics_registry()
    histogram = registry.get_histogram("http_request_duration_seconds")
    if histogram:
        histogram.observe(duration, labels={"method": method, "endpoint": endpoint})


def record_error(
    method: str,
    endpoint: str,
    error_type: str,
) -> None:
    """Record an HTTP request error."""
    registry = get_metrics_registry()
    counter = registry.get_counter("http_request_errors_total")
    if counter:
        counter.inc(
            labels={"method": method, "endpoint": endpoint, "error_type": error_type}
        )


def record_db_query(
    operation: str,
    table: str,
    duration: float,
) -> None:
    """Record a database query."""
    registry = get_metrics_registry()

    counter = registry.get_counter("db_queries_total")
    if counter:
        counter.inc(labels={"operation": operation, "table": table})

    histogram = registry.get_histogram("db_query_duration_seconds")
    if histogram:
        histogram.observe(duration, labels={"operation": operation})


def record_cache_hit(cache_name: str = "default") -> None:
    """Record a cache hit."""
    registry = get_metrics_registry()
    counter = registry.get_counter("cache_hits_total")
    if counter:
        counter.inc(labels={"cache_name": cache_name})


def record_cache_miss(cache_name: str = "default") -> None:
    """Record a cache miss."""
    registry = get_metrics_registry()
    counter = registry.get_counter("cache_misses_total")
    if counter:
        counter.inc(labels={"cache_name": cache_name})


def set_app_info(version: str | None = None, environment: str | None = None) -> None:
    """Set application info gauge."""
    registry = get_metrics_registry()
    gauge = registry.get_gauge("app_info")
    if gauge:
        version = version or getattr(settings, "VERSION", "unknown") or "unknown"
        environment = (
            environment or getattr(settings, "ENVIRONMENT", "unknown") or "unknown"
        )
        gauge.set(1.0, labels={"version": version, "environment": environment})


def timed(
    metric_name: str | None = None,
    labels: dict[str, str] | None = None,
) -> Callable:
    """Decorator to measure function execution time.

    Args:
        metric_name: Name of the histogram metric. Defaults to function name.
        labels: Additional labels for the metric.

    Returns:
        Decorated function.

    Example:
        ```python
        @timed("payment_processing_seconds", {"provider": "stripe"})
        def process_payment(amount):
            # Your code here
            pass
        ```
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                registry = get_metrics_registry()
                name = metric_name or f"{func.__module__}_{func.__name__}_seconds"

                # Register histogram if not exists
                histogram = registry.get_histogram(name)
                if histogram is None:
                    histogram = registry.register_histogram(
                        name,
                        f"Execution time of {func.__name__}",
                        list(labels.keys()) if labels else None,
                    )

                histogram.observe(duration, labels)

        return wrapper

    return decorator

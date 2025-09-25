"""Performance monitoring utilities."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import psutil
from django.db import connection

from .metrics import record_database_query, record_response_time

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor application performance metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.query_count_start = len(connection.queries)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        query_count_end = len(connection.queries)

        execution_time = end_time - self.start_time
        query_count = query_count_end - self.query_count_start

        logger.info(
            "Performance: %.3fs execution time, %d database queries",
            execution_time,
            query_count,
        )

        # Record database query metrics
        if query_count > 0:
            record_database_query(
                query_type="mixed",
                table="multiple",
                duration=execution_time,
                query_count=query_count,
            )


def performance_monitor(func: Callable) -> Callable:
    """Decorator to monitor function performance."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceMonitor():
            return func(*args, **kwargs)

    return wrapper


def track_performance(endpoint: str, method: str = "GET"):
    """Decorator to track API endpoint performance."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                response_time = end_time - start_time

                # Record response time
                record_response_time(endpoint, method, response_time)

        return wrapper

    return decorator


def memory_usage() -> dict[str, Any]:
    """Get current memory usage statistics."""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss": memory_info.rss,  # Resident Set Size
            "vms": memory_info.vms,  # Virtual Memory Size
            "percent": process.memory_percent(),
            "available": psutil.virtual_memory().available,
            "total": psutil.virtual_memory().total,
        }
    except Exception as e:
        logger.error("Failed to get memory usage: %s", e)
        return {}


def cpu_usage() -> dict[str, Any]:
    """Get current CPU usage statistics."""
    try:
        return {
            "percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count(),
            "load_avg": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
        }
    except Exception as e:
        logger.error("Failed to get CPU usage: %s", e)
        return {}


def system_stats() -> dict[str, Any]:
    """Get comprehensive system statistics."""
    return {
        "memory": memory_usage(),
        "cpu": cpu_usage(),
        "disk": disk_usage(),
        "network": network_stats(),
    }


def disk_usage() -> dict[str, Any]:
    """Get disk usage statistics."""
    try:
        disk = psutil.disk_usage("/")
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.used / disk.total * 100,
        }
    except Exception as e:
        logger.error("Failed to get disk usage: %s", e)
        return {}


def network_stats() -> dict[str, Any]:
    """Get network statistics."""
    try:
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }
    except Exception as e:
        logger.error("Failed to get network stats: %s", e)
        return {}

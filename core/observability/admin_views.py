"""Staff admin views for the observability stack.

Renders health checks and Prometheus metrics as Unfold admin pages.
The raw API endpoints (``/api/health/detailed`` and ``/api/metrics``)
stay unchanged for scrapers and dashboards.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .health import run_health_checks
from .metrics import get_metrics_registry


def _fmt_value(value: float) -> str:
    """Format a metric value for display."""
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}"


def _label_text(labels: dict[str, str]) -> str:
    """Render a label dict as a compact ``k=v`` string."""
    if not labels:
        return "—"
    return ", ".join(f"{k}={v}" for k, v in sorted(labels.items()))


def _render_samples(samples: list[tuple[dict[str, str], float]]) -> list[dict]:
    """Format metric samples for the template."""
    return [
        {"labels": _label_text(labels), "value": _fmt_value(value)}
        for labels, value in samples
    ]


def _histogram_rows(samples) -> list[dict]:
    """Group histogram samples into one row per label set.

    The registry emits one sample per bucket plus ``_sum`` and ``_count``
    rows per label set; this collapses them into count / sum / average.
    """
    rows: dict[tuple, dict] = {}
    for metric_name, labels, value in samples:
        key = tuple(sorted(labels.items()))
        row = rows.setdefault(
            key, {"labels": _label_text(labels), "count": 0, "sum": 0.0}
        )
        if metric_name.endswith("_sum"):
            row["sum"] = value
        elif metric_name.endswith("_count"):
            row["count"] = int(value)
    for row in rows.values():
        row["avg_ms"] = (
            round(row["sum"] * 1000 / row["count"], 2) if row["count"] else None
        )
        row["sum"] = _fmt_value(row["sum"])
    return sorted(rows.values(), key=lambda row: row["labels"])


def _total(samples: list[tuple[dict[str, str], float]]) -> float:
    """Sum the values of a metric's samples."""
    return sum(value for _, value in samples)


@staff_member_required
@require_GET
def health_admin_view(request):
    """Render the health check results inside the Unfold admin."""
    result = run_health_checks()
    checks = [
        {
            "name": check.name,
            "status": check.status.value,
            "message": check.message or "",
            "response_time_ms": (
                round(check.response_time_ms, 1)
                if check.response_time_ms is not None
                else None
            ),
            "details": check.details or {},
        }
        for check in result.checks
    ]
    context = admin.site.each_context(request)
    context.update(
        {
            "title": "Health Check",
            "subtitle": f"{result.status.value} — {len(checks)} checks",
            "overall_status": result.status.value,
            "version": result.version,
            "environment": result.environment,
            "checks": checks,
        }
    )
    return render(request, "admin/observability/health.html", context)


@staff_member_required
@require_GET
def metrics_admin_view(request):
    """Render the metrics registry inside the Unfold admin."""
    snapshot = get_metrics_registry().snapshot()

    summary: dict[str, float] = {}
    for item in snapshot["counters"]:
        if item["name"] == "http_requests_total":
            summary["requests"] = _total(item["samples"])
        elif item["name"] == "http_request_errors_total":
            summary["errors"] = _total(item["samples"])
        elif item["name"] == "db_queries_total":
            summary["db_queries"] = _total(item["samples"])
        elif item["name"] == "cache_hits_total":
            summary["cache_hits"] = _total(item["samples"])
        elif item["name"] == "cache_misses_total":
            summary["cache_misses"] = _total(item["samples"])

    simple_metrics = [
        {
            "name": item["name"],
            "description": item["description"],
            "kind": kind,
            "samples": _render_samples(item["samples"]),
        }
        for kind in ("counter", "gauge")
        for item in snapshot[f"{kind}s"]
    ]
    histograms = [
        {
            "name": item["name"],
            "description": item["description"],
            "rows": _histogram_rows(item["samples"]),
        }
        for item in snapshot["histograms"]
    ]

    context = admin.site.each_context(request)
    context.update(
        {
            "title": "API Metrics",
            "subtitle": "Prometheus metrics collected at runtime",
            "summary": summary,
            "simple_metrics": simple_metrics,
            "histograms": histograms,
        }
    )
    return render(request, "admin/observability/metrics.html", context)

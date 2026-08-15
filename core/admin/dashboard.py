"""Admin dashboard stats for django-unfold.

Provides a DASHBOARD_CALLBACK that returns stats cards for the admin index.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def dashboard_callback(request, context):
    """Return dashboard stats for the admin index page.

    Returns a list of dicts that django-unfold renders as dashboard cards.
    Each dict can be a stats card, chart, or list widget.
    """
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── User stats ──────────────────────────────────────────────────
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
    new_users_month = User.objects.filter(date_joined__gte=month_ago).count()

    # ── Audit stats ─────────────────────────────────────────────────
    try:
        from core.audit.models import AuditLog

        recent_audit_count = AuditLog.objects.filter(created_at__gte=week_ago).count()
        total_audit_count = AuditLog.objects.count()
    except (ImportError, Exception):
        recent_audit_count = 0
        total_audit_count = 0

    # ── Build dashboard cards ───────────────────────────────────────
    context["stats_cards"] = [
        {
            "title": "Total Users",
            "value": total_users,
            "description": f"{new_users_week} new this week",
            "icon": "people",
            "color": "primary",
        },
        {
            "title": "Active Users",
            "value": active_users,
            "description": f"{staff_users} staff members",
            "icon": "person_check",
            "color": "green",
        },
        {
            "title": "New Users (30d)",
            "value": new_users_month,
            "description": f"{new_users_week} this week",
            "icon": "person_add",
            "color": "blue",
        },
        {
            "title": "Audit Events (7d)",
            "value": recent_audit_count,
            "description": f"{total_audit_count} total",
            "icon": "history",
            "color": "orange",
        },
    ]

    # ── Recent activity list ─────────────────────────────────────────
    context["recent_activity"] = _get_recent_activity(now)

    # ── Quick links ──────────────────────────────────────────────────
    context["quick_links"] = [
        {
            "title": "Health Check",
            "url": "/admin/observability/health/",
            "icon": "monitor_heart",
        },
        {
            "title": "API Metrics",
            "url": "/admin/observability/metrics/",
            "icon": "bar_chart",
        },
        {"title": "API Docs", "url": "/api/docs", "icon": "description"},
        {
            "title": "Codebase Atlas",
            "url": "/admin/atlas/",
            "icon": "map",
        },
    ]
    if getattr(settings, "FLOWER_URL", ""):
        context["quick_links"].append(
            {
                "title": "Flower Tasks",
                "url": settings.FLOWER_URL,
                "icon": "local_shipping",
            }
        )

    return context


def _get_recent_activity(now) -> list[dict]:
    """Get recent audit log entries for the dashboard."""
    try:
        from core.audit.models import AuditLog

        entries = AuditLog.objects.select_related("user").order_by("-timestamp")[:10]
        return [
            {
                "user": entry.user.email if entry.user else "System",
                "action": entry.action,
                "target": str(entry.object_repr)[:60] if entry.object_repr else "",
                "time": entry.timestamp.strftime("%b %d, %H:%M"),
            }
            for entry in entries
        ]
    except (ImportError, Exception):
        return []

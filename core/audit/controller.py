"""API Controller for Audit Logs.

Provides API endpoints for querying and exporting audit logs.
All endpoints require admin/staff permissions.
"""

import logging
from datetime import timedelta
from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja_extra import api_controller, http_get
from ninja_extra.pagination import paginate

from api.decorators import handle_exceptions, log_api_call
from api.permissions import IsAdminUser
from core.audit.models import AuditAction, AuditLog
from core.audit.schemas import (
    AuditLogListSchema,
    AuditLogSchema,
    AuditLogStatsSchema,
)

logger = logging.getLogger(__name__)


@api_controller("/audit", tags=["Audit Logs"], permissions=[IsAdminUser])
class AuditLogController:
    """Controller for managing audit logs.

    All endpoints require admin/staff permissions.
    Audit logs are read-only to maintain integrity.
    """

    @paginate
    @http_get("/", response=list[AuditLogListSchema])
    @handle_exceptions()
    @log_api_call()
    def list_audit_logs(
        self,
        action: str | None = None,
        user_email: str | None = None,
        model_name: str | None = None,
        object_id: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        search: str | None = None,
        ordering: str | None = None,
    ):
        """List audit logs with filtering and pagination.

        Args:
            action: Filter by action type (CREATE, UPDATE, DELETE, etc.)
            user_email: Filter by user email
            model_name: Filter by model name
            object_id: Filter by object ID
            ip_address: Filter by IP address
            success: Filter by success status
            start_date: Filter logs from this date (ISO format)
            end_date: Filter logs until this date (ISO format)
            search: Search in description and paths
            ordering: Order by field (prefix with - for descending)
        """
        queryset = AuditLog.objects.all()

        # Apply filters
        if action:
            queryset = queryset.filter(action=action)

        if user_email:
            queryset = queryset.filter(user_email__icontains=user_email)

        if model_name:
            queryset = queryset.filter(model_name__iexact=model_name)

        if object_id:
            queryset = queryset.filter(object_id=object_id)

        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        if success is not None:
            queryset = queryset.filter(success=success)

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)

        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        if search:
            queryset = queryset.filter(
                action_description__icontains=search
            ) | queryset.filter(request_path__icontains=search)

        # Apply ordering
        if ordering:
            valid_orderings = [
                "timestamp",
                "-timestamp",
                "action",
                "-action",
                "model_name",
                "-model_name",
                "user_email",
                "-user_email",
            ]
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-timestamp")

        return queryset

    @http_get("/{audit_log_id}", response={200: AuditLogSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_audit_log(self, audit_log_id: UUID):
        """Get a specific audit log entry by ID.

        Args:
            audit_log_id: UUID of the audit log entry
        """
        audit_log = get_object_or_404(AuditLog, id=audit_log_id)
        return 200, AuditLogSchema.from_orm(audit_log)

    @http_get("/stats/summary", response={200: AuditLogStatsSchema})
    @handle_exceptions()
    @log_api_call()
    def get_audit_stats(
        self,
        days: int = 30,
    ):
        """Get audit log statistics.

        Args:
            days: Number of days to include in statistics (default: 30)
        """
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Base queryset for the time range
        queryset = AuditLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        )

        # Total logs
        total_logs = queryset.count()

        # Logs by action
        logs_by_action = dict(
            queryset.values("action")
            .annotate(count=Count("id"))
            .values_list("action", "count")
        )

        # Logs by model
        logs_by_model = dict(
            queryset.exclude(model_name="")
            .values("model_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
            .values_list("model_name", "count")
        )

        # Logs by success
        logs_by_success = {
            "success": queryset.filter(success=True).count(),
            "failed": queryset.filter(success=False).count(),
        }

        # Recent failed logins (last 24 hours)
        recent_failed_logins = AuditLog.objects.filter(
            action=AuditAction.LOGIN_FAILED,
            timestamp__gte=timezone.now() - timedelta(hours=24),
        ).count()

        # Unique users
        unique_users = (
            queryset.exclude(user_email="").values("user_email").distinct().count()
        )

        # Unique IPs
        unique_ips = (
            queryset.exclude(ip_address__isnull=True)
            .values("ip_address")
            .distinct()
            .count()
        )

        return 200, AuditLogStatsSchema(
            total_logs=total_logs,
            logs_by_action=logs_by_action,
            logs_by_model=logs_by_model,
            logs_by_success=logs_by_success,
            recent_failed_logins=recent_failed_logins,
            unique_users=unique_users,
            unique_ips=unique_ips,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
        )

    @http_get("/object/{model_name}/{object_id}", response=list[AuditLogListSchema])
    @handle_exceptions()
    @log_api_call()
    def get_object_history(self, model_name: str, object_id: str):
        """Get the complete audit history for a specific object.

        Args:
            model_name: Name of the model
            object_id: ID of the object
        """
        queryset = AuditLog.objects.filter(
            model_name__iexact=model_name,
            object_id=object_id,
        ).order_by("-timestamp")

        return [AuditLogListSchema.from_orm(log) for log in queryset]

    @http_get("/user/{user_email}", response=list[AuditLogListSchema])
    @handle_exceptions()
    @log_api_call()
    def get_user_activity(self, user_email: str, limit: int = 100):
        """Get audit logs for a specific user.

        Args:
            user_email: Email of the user
            limit: Maximum number of records to return (default: 100)
        """
        queryset = AuditLog.objects.filter(user_email__iexact=user_email).order_by(
            "-timestamp"
        )[:limit]

        return [AuditLogListSchema.from_orm(log) for log in queryset]

    @http_get("/ip/{ip_address}", response=list[AuditLogListSchema])
    @handle_exceptions()
    @log_api_call()
    def get_ip_activity(self, ip_address: str, limit: int = 100):
        """Get audit logs from a specific IP address.

        Args:
            ip_address: IP address to look up
            limit: Maximum number of records to return (default: 100)
        """
        queryset = AuditLog.objects.filter(ip_address=ip_address).order_by(
            "-timestamp"
        )[:limit]

        return [AuditLogListSchema.from_orm(log) for log in queryset]

    @http_get("/actions", response={200: list[dict]})
    @handle_exceptions()
    @log_api_call()
    def list_action_types(self):
        """List all available audit action types."""
        return 200, [
            {"value": choice.value, "label": choice.label} for choice in AuditAction
        ]

    @http_get("/models", response={200: list[str]})
    @handle_exceptions()
    @log_api_call()
    def list_audited_models(self):
        """List all models that have audit log entries."""
        models = (
            AuditLog.objects.exclude(model_name="")
            .values_list("model_name", flat=True)
            .distinct()
            .order_by("model_name")
        )
        return 200, list(models)

    @http_get("/failed-logins", response=list[AuditLogListSchema])
    @handle_exceptions()
    @log_api_call()
    def get_failed_logins(self, hours: int = 24, limit: int = 100):
        """Get recent failed login attempts.

        Useful for security monitoring and detecting brute force attacks.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)
        """
        since = timezone.now() - timedelta(hours=hours)
        queryset = AuditLog.objects.filter(
            action=AuditAction.LOGIN_FAILED,
            timestamp__gte=since,
        ).order_by("-timestamp")[:limit]

        return [AuditLogListSchema.from_orm(log) for log in queryset]

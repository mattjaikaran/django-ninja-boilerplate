"""Feature Flag Controller.

API endpoints for managing and checking feature flags.
"""

import logging
from uuid import UUID

from ninja_extra import (
    api_controller,
    http_delete,
    http_get,
    http_patch,
    http_post,
    http_put,
)
from ninja_extra.pagination import paginate
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call

from .models import FeatureFlag, FeatureFlagAuditLog
from .schemas import (
    BulkFlagResponseSchema,
    BulkFlagToggleSchema,
    CheckFlagSchema,
    FeatureFlagCreateSchema,
    FeatureFlagListSchema,
    FeatureFlagSchema,
    FeatureFlagUpdateSchema,
    FeatureFlagWithAuditSchema,
    FlagAuditLogSchema,
    FlagStatusSchema,
    RolloutUpdateSchema,
    UserFlagSchema,
    UserFlagsSchema,
)
from .service import feature_flag_service

logger = logging.getLogger(__name__)


# =============================================================================
# Admin Controller - Full CRUD for managing feature flags
# =============================================================================


@api_controller("/admin/feature-flags", tags=["Feature Flags (Admin)"], auth=JWTAuth())
class FeatureFlagAdminController:
    """Admin controller for managing feature flags.

    Requires authentication and provides full CRUD operations.
    """

    @http_post("/", response={201: FeatureFlagSchema, 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_flag(self, request, payload: FeatureFlagCreateSchema):
        """Create a new feature flag."""
        flag = feature_flag_service.create_flag(
            name=payload.name,
            description=payload.description,
            flag_type=payload.flag_type.value,
            enabled=payload.enabled,
            rollout_percentage=payload.rollout_percentage,
            variants=payload.variants,
            conditions=payload.conditions,
            user=request.user,
            user_ids=payload.user_ids,
            excluded_user_ids=payload.excluded_user_ids,
            default_variant=payload.default_variant,
            environments=payload.environments,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            tags=payload.tags,
            metadata=payload.metadata,
        )
        return 201, flag

    @paginate
    @http_get("/", response=list[FeatureFlagListSchema])
    @handle_exceptions()
    @log_api_call()
    def list_flags(
        self,
        request,
        enabled: bool | None = None,
        flag_type: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ):
        """List all feature flags with optional filtering."""
        queryset = FeatureFlag.objects.all()

        if enabled is not None:
            queryset = queryset.filter(enabled=enabled)

        if flag_type:
            queryset = queryset.filter(flag_type=flag_type)

        if tag:
            queryset = queryset.filter(tags__contains=[tag])

        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(
                description__icontains=search
            )

        return queryset.order_by("name")

    @http_get("/{flag_id}", response={200: FeatureFlagWithAuditSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_flag(self, request, flag_id: UUID):
        """Get a feature flag by ID with audit logs."""
        flag = feature_flag_service.get_by_id_or_raise(flag_id)

        # Get recent audit logs
        audit_logs = FeatureFlagAuditLog.objects.filter(feature_flag=flag).order_by(
            "-created_at"
        )[:20]

        # Build response with audit logs
        response_data = FeatureFlagSchema.from_orm(flag).model_dump()
        response_data["audit_logs"] = [
            FlagAuditLogSchema.from_orm(log).model_dump() for log in audit_logs
        ]

        return 200, response_data

    @http_get("/name/{flag_name}", response={200: FeatureFlagSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_flag_by_name(self, request, flag_name: str):
        """Get a feature flag by name."""
        flag = feature_flag_service.get_flag(flag_name)
        if flag is None:
            return 404, {
                "error": "Not found",
                "message": f"Flag '{flag_name}' not found",
            }
        return 200, flag

    @http_put("/{flag_id}", response={200: FeatureFlagSchema, 400: dict, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_flag(self, request, flag_id: UUID, payload: FeatureFlagUpdateSchema):
        """Update a feature flag."""
        update_data = payload.model_dump(exclude_unset=True)

        # Convert enum to string if present
        if update_data.get("flag_type"):
            update_data["flag_type"] = update_data["flag_type"].value

        flag = feature_flag_service.update_flag(flag_id, update_data, request.user)
        return 200, flag

    @http_patch("/{flag_id}/toggle", response={200: FeatureFlagSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def toggle_flag(self, request, flag_id: UUID, enabled: bool | None = None):
        """Toggle a feature flag on or off."""
        flag = feature_flag_service.get_by_id_or_raise(flag_id)
        flag = feature_flag_service.toggle_flag(flag.name, enabled, request.user)
        return 200, flag

    @http_patch(
        "/{flag_id}/rollout", response={200: FeatureFlagSchema, 400: dict, 404: dict}
    )
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_rollout(self, request, flag_id: UUID, payload: RolloutUpdateSchema):
        """Update rollout percentage for a feature flag."""
        flag = feature_flag_service.get_by_id_or_raise(flag_id)
        flag = feature_flag_service.set_rollout_percentage(
            flag.name, payload.percentage, request.user
        )
        return 200, flag

    @http_post("/{flag_id}/users", response={200: FeatureFlagSchema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def add_user_to_flag(self, request, flag_id: UUID, payload: UserFlagSchema):
        """Add a user to a feature flag's enabled list."""
        flag = feature_flag_service.get_by_id_or_raise(flag_id)
        flag = feature_flag_service.add_user_to_flag(
            flag.name, payload.user_id, request.user
        )
        return 200, flag

    @http_delete(
        "/{flag_id}/users/{user_id}", response={200: FeatureFlagSchema, 404: dict}
    )
    @handle_exceptions()
    @log_api_call()
    def remove_user_from_flag(self, request, flag_id: UUID, user_id: str):
        """Remove a user from a feature flag's enabled list."""
        flag = feature_flag_service.get_by_id_or_raise(flag_id)
        flag = feature_flag_service.remove_user_from_flag(
            flag.name, user_id, request.user
        )
        return 200, flag

    @http_delete("/{flag_id}", response={204: None, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_flag(self, request, flag_id: UUID):
        """Delete a feature flag."""
        feature_flag_service.delete_flag(flag_id, request.user)
        return 204, None

    @http_post("/bulk/toggle", response={200: BulkFlagResponseSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def bulk_toggle_flags(self, request, payload: BulkFlagToggleSchema):
        """Bulk toggle multiple feature flags."""
        updated = 0
        failed = []
        errors = {}

        for flag_name in payload.flag_names:
            try:
                feature_flag_service.toggle_flag(
                    flag_name, payload.enabled, request.user
                )
                updated += 1
            except Exception as e:
                failed.append(flag_name)
                errors[flag_name] = str(e)

        return 200, BulkFlagResponseSchema(
            success=len(failed) == 0,
            updated=updated,
            failed=failed,
            errors=errors,
        )


# =============================================================================
# User Controller - Check flag status
# =============================================================================


@api_controller("/feature-flags", tags=["Feature Flags"])
class FeatureFlagController:
    """Controller for checking feature flag status.

    Public endpoints for applications to check flag status.
    """

    @http_post("/check", response={200: FlagStatusSchema, 404: dict}, auth=None)
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def check_flag(self, request, payload: CheckFlagSchema):
        """Check if a feature flag is enabled.

        This endpoint can be used by applications to check flag status.
        If the request is authenticated, user-specific evaluation is performed.
        """
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

        flag = feature_flag_service.get_flag(payload.flag_name)
        if flag is None:
            return 404, {
                "error": "Not found",
                "message": f"Flag '{payload.flag_name}' not found",
            }

        enabled = feature_flag_service.is_enabled(
            payload.flag_name,
            user=user,
            context=payload.context,
        )

        # Get variant if it's an A/B test
        variant = None
        if flag.flag_type == "ab_test":
            variant = feature_flag_service.get_variant(payload.flag_name, user)

        return 200, FlagStatusSchema(
            flag_name=payload.flag_name,
            enabled=enabled,
            variant=variant,
        )

    @http_get("/me", response={200: UserFlagsSchema}, auth=JWTAuth())
    @handle_exceptions()
    @log_api_call()
    def get_my_flags(self, request):
        """Get all feature flags for the authenticated user.

        Returns a dictionary of all enabled flags and their status/variant
        for the current user.
        """
        flags = feature_flag_service.get_flags_for_user(request.user)
        return 200, UserFlagsSchema(flags=flags)

    @http_get("/{flag_name}", response={200: FlagStatusSchema, 404: dict}, auth=None)
    @handle_exceptions()
    @log_api_call()
    def get_flag_status(self, request, flag_name: str):
        """Get the status of a specific feature flag.

        If authenticated, returns user-specific status.
        """
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

        flag = feature_flag_service.get_flag(flag_name)
        if flag is None:
            return 404, {
                "error": "Not found",
                "message": f"Flag '{flag_name}' not found",
            }

        enabled = feature_flag_service.is_enabled(flag_name, user=user)

        variant = None
        if flag.flag_type == "ab_test":
            variant = feature_flag_service.get_variant(flag_name, user)

        return 200, FlagStatusSchema(
            flag_name=flag_name,
            enabled=enabled,
            variant=variant,
        )

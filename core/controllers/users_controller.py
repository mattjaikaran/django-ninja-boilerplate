"""Users controller — admin-level user management endpoints.

Routes:
    POST /users/superuser      — create a superuser account
    GET  /users/               — list all users (paginated, filterable)
    GET  /users/{user_id}      — retrieve a single user by UUID
    PUT  /users/{user_id}      — update a user's profile fields
    DELETE /users/{user_id}    — permanently delete a user
    GET  /users/staff          — list staff users (paginated)
    GET  /users/active         — list active users (paginated)

All endpoints are decorated with ``handle_exceptions`` and ``log_api_call``
for consistent error handling and audit logging.
"""

import logging
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate

from api.decorators import handle_exceptions, log_api_call
from core.schemas import (
    UserSchema,
    UserSignupSchema,
    UserUpdateSchema,
)

User = get_user_model()

logger = logging.getLogger(__name__)


# the tag customizes Swagger or else it will be default lowercase
# ie - users
@api_controller("/users", tags=["Users"])
class UserController:
    """HTTP controller for admin-level user management.

    Provides CRUD operations over the User model. All endpoints are
    intended for staff/admin use and are not protected by JWT by default —
    add ``auth=JWTAuth()`` and staff permission checks if needed in
    production.
    """

    @http_post("/superuser", response={201: UserSchema, 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_superuser(self, request, payload: UserSignupSchema):
        """Create a superuser account.

        Validates the password and enforces the constraint that superusers
        must also have ``is_staff=True``.

        Args:
            request: The HTTP request object.
            payload: Validated signup data. ``is_superuser`` and ``is_staff``
                flags must be consistent (both True for superusers).

        Returns:
            Tuple of (201, UserSchema) on success, (400, error_dict) on
            validation failure, or (500, error_dict) on unexpected error.

        Raises:
            ValueError: If ``is_superuser`` is True but ``is_staff`` is False.
        """
        validate_password(payload.password)
        if payload.is_superuser and not payload.is_staff:
            raise ValueError("Superuser must have is_staff=True.")

        user = User.objects.create_superuser(  # type: ignore[attr-defined]
            **payload.model_dump(exclude_unset=True),
            is_staff=True,
            is_superuser=True,
        )
        return 201, UserSchema.from_orm(user)

    @http_get("/{user_id}", response={200: UserSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_user(self, user_id: UUID):
        """Retrieve a single user by UUID.

        Args:
            user_id: The UUID primary key of the user.

        Returns:
            Tuple of (200, UserSchema) on success or (404, error_dict) if the
            user does not exist.
        """
        user = get_object_or_404(User, id=user_id)
        return 200, UserSchema.from_orm(user)

    @paginate
    @http_get("/", response=list[UserSchema])
    @handle_exceptions()
    @log_api_call()
    def list_users(
        self,
        is_active: bool | None = None,
        is_staff: bool | None = None,
        is_superuser: bool | None = None,
        ordering: str | None = None,
    ):
        """List all users with optional filtering and ordering.

        Args:
            is_active: When provided, filter by the user's active status.
            is_staff: When provided, filter by staff membership.
            is_superuser: When provided, filter by superuser status.
            ordering: Sort field. Accepted values: ``username``, ``-username``,
                ``email``, ``-email``, ``date_joined``, ``-date_joined``,
                ``last_login``, ``-last_login``. Unknown values are silently
                ignored.

        Returns:
            Paginated queryset of matching User instances.
        """
        queryset = User.objects.all()

        # Apply filters
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        if is_staff is not None:
            queryset = queryset.filter(is_staff=is_staff)

        if is_superuser is not None:
            queryset = queryset.filter(is_superuser=is_superuser)

        # Apply ordering
        if ordering:
            valid_orderings = [
                "username",
                "-username",
                "email",
                "-email",
                "date_joined",
                "-date_joined",
                "last_login",
                "-last_login",
            ]
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)

        return queryset

    @http_put("/{user_id}", response={200: UserSchema, 400: dict, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_user(self, user_id: UUID, payload: UserUpdateSchema):
        """Update an existing user's profile fields.

        Only fields that are explicitly set in the request body are applied
        (``exclude_unset=True``).

        Args:
            user_id: The UUID primary key of the user to update.
            payload: Validated update data. Only non-omitted fields are written.

        Returns:
            Tuple of (200, UserSchema) on success, (400, error_dict) on
            validation failure, or (404, error_dict) if the user does not exist.
        """
        user = get_object_or_404(User, id=user_id)
        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, attr, value)
        user.save()
        return 200, UserSchema.from_orm(user)

    @http_delete("/{user_id}", response={204: None})
    @handle_exceptions()
    @log_api_call()
    def delete_user(self, user_id: UUID):
        """Permanently delete a user.

        This is a hard delete — the user record is removed from the database.
        Consider soft-delete alternatives (``SoftDeleteMixin``) for
        production use cases that require audit trails.

        Args:
            user_id: The UUID primary key of the user to delete.

        Returns:
            Tuple of (204, None) on success or (404, error_dict) if the user
            does not exist.
        """
        user = get_object_or_404(User, id=user_id)
        user.delete()
        return 204, None

    @paginate
    @http_get("/staff", response=list[UserSchema])
    @handle_exceptions()
    @log_api_call()
    def list_staff_users(self):
        """List all staff users, ordered by most recently joined.

        Returns:
            Paginated queryset of User instances where ``is_staff=True``,
            ordered by ``-date_joined``.
        """
        return User.objects.filter(is_staff=True).order_by("-date_joined")

    @paginate
    @http_get("/active", response=list[UserSchema])
    @handle_exceptions()
    @log_api_call()
    def list_active_users(self):
        """List all active users, ordered by most recent login.

        Returns:
            Paginated queryset of User instances where ``is_active=True``,
            ordered by ``-last_login``.
        """
        return User.objects.filter(is_active=True).order_by("-last_login")

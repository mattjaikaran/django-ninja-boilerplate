import logging
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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
    @http_post("/signup", response={201: UserSignupSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def signup(self, request: UserSignupSchema):
        """Create a new user account."""
        if User.objects.filter(username=request.username).exists():
            raise ValidationError("A user with this username already exists.")

        validate_password(request.password)
        if User.objects.filter(email=request.email).exists():
            raise ValidationError("A user with this email already exists.")

        user = User.objects.create_user(
            **request.dict(exclude_unset=True),  # Unpack request attributes
            is_staff=False,
            is_superuser=False,
        )
        return 201, UserSchema.from_orm(user)

    @http_post("/superuser", response={201: UserSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_superuser(self, request: UserSignupSchema):
        """Create a superuser account (admin only)."""
        validate_password(request.password)
        if request.is_superuser and not request.is_staff:
            raise ValueError("Superuser must have is_staff=True.")

        user = User.objects.create_superuser(
            **request.dict(exclude_unset=True),
            is_staff=True,
            is_superuser=True,
        )
        return 201, UserSchema.from_orm(user)

    @http_get("/{user_id}", response={200: UserSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_user(self, user_id: UUID):
        """Get a specific user by ID."""
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
        """List users with filtering and pagination."""
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
        """Update a user (admin only)."""
        user = get_object_or_404(User, id=user_id)
        for attr, value in payload.dict(exclude_unset=True).items():
            setattr(user, attr, value)
        user.save()
        return 200, UserSchema.from_orm(user)

    @http_delete("/{user_id}", response={204: None})
    @handle_exceptions()
    @log_api_call()
    def delete_user(self, user_id: UUID):
        """Delete a user (admin only)."""
        user = get_object_or_404(User, id=user_id)
        user.delete()
        return 204, None

    @paginate
    @http_get("/staff", response=list[UserSchema])
    @handle_exceptions()
    @log_api_call()
    def list_staff_users(self):
        """List staff users."""
        queryset = User.objects.filter(is_staff=True).order_by("-date_joined")
        return queryset

    @paginate
    @http_get("/active", response=list[UserSchema])
    @handle_exceptions()
    @log_api_call()
    def list_active_users(self):
        """List active users."""
        queryset = User.objects.filter(is_active=True).order_by("-last_login")
        return queryset

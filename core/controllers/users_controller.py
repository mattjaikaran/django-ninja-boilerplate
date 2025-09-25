import logging
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    admin_endpoint,
    delete_endpoint,
    detail_endpoint,
    handle_exceptions,
    list_endpoint,
    log_api_call,
    search_and_filter,
    update_endpoint,
)
from api.search_filters import UserSearchFilter, get_user_search_engine
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
    @handle_exceptions
    @log_api_call()
    @http_post("/signup", response={201: UserSignupSchema, 400: dict})
    def signup(self, request: UserSignupSchema):
        if User.objects.filter(username=request.username).exists():
            raise ValidationError("A user with this username already exists.")

        validate_password(request.password)
        if User.objects.filter(email=request.email).exists():
            raise ValidationError("A user with this email already exists.")
        if User.objects.filter(username=request.username).exists():
            raise ValidationError("A user with this username already exists.")

        user = User.objects.create_user(
            **request.dict(exclude_unset=True),  # Unpack request attributes
            is_staff=False,
            is_superuser=False,
        )
        return 201, UserSchema.from_orm(user)

    @admin_endpoint()
    @http_post("/superuser", response={201: UserSchema, 400: dict})
    def create_superuser(self, request: UserSignupSchema):
        validate_password(request.password)
        if request.is_superuser and not request.is_staff:
            raise ValueError("Superuser must have is_staff=True.")

        user = User.objects.create_superuser(
            **request.dict(exclude_unset=True),
            is_staff=True,
            is_superuser=True,
        )
        return 201, UserSchema.from_orm(user)

    @detail_endpoint()
    @http_get("/{user_id}", response={200: UserSchema, 404: dict})
    def get_user(self, user_id: UUID):
        user = get_object_or_404(User, id=user_id)
        return 200, UserSchema.from_orm(user)

    @list_endpoint(
        enable_pagination=True,
        require_admin=True,
    )
    @search_and_filter(
        search_fields=["username", "email", "first_name", "last_name"],
        filter_fields={
            "is_active": "boolean",
            "is_staff": "boolean",
            "is_superuser": "boolean",
        },
        ordering_fields=["username", "email", "date_joined", "last_login"],
    )
    @http_get("/", response={200: list[UserSchema]})
    def list_users(self, request, filters: UserSearchFilter = None):
        queryset = User.objects.all()

        if filters:
            search_engine = get_user_search_engine()
            queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @update_endpoint(require_admin=True)
    @http_put("/{user_id}", response={200: UserSchema, 400: dict, 404: dict})
    def update_user(self, user_id: UUID, payload: UserUpdateSchema):
        user = get_object_or_404(User, id=user_id)
        for attr, value in payload.dict(exclude_unset=True).items():
            setattr(user, attr, value)
        user.save()
        return 200, UserSchema.from_orm(user)

    @delete_endpoint(require_admin=True)
    @http_delete("/{user_id}", response={204: dict, 404: dict})
    def delete_user(self, user_id: UUID):
        user = get_object_or_404(User, id=user_id)
        user.delete()
        return 204, {"message": "User deleted successfully"}

    @list_endpoint(
        enable_pagination=True,
        require_admin=True,
    )
    @http_get("/search", response={200: list[UserSchema]})
    def search_users(self, request, filters: UserSearchFilter):
        """Advanced search endpoint for users."""
        queryset = User.objects.all()

        search_engine = get_user_search_engine()
        queryset = search_engine.apply_search(queryset, filters)

        return 200, queryset

    @list_endpoint(
        enable_pagination=True,
        require_admin=True,
    )
    @http_get("/staff", response={200: list[UserSchema]})
    def list_staff_users(self, request):
        """List staff users."""
        queryset = User.objects.filter(is_staff=True).order_by("-date_joined")
        return 200, queryset

    @list_endpoint(
        enable_pagination=True,
        require_admin=True,
    )
    @http_get("/active", response={200: list[UserSchema]})
    def list_active_users(self, request):
        """List active users."""
        queryset = User.objects.filter(is_active=True).order_by("-last_login")
        return 200, queryset

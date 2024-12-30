from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from .schemas import (
    UserSchema,
    UserSignupSchema,
    UserUpdateSchema,
)

User = get_user_model()


# the tag customizes Swagger or else it will be default lowercase
# ie - users
@api_controller("/users", tags=["Users"])
class UserController:
    @http_post("/signup", response={201: UserSignupSchema, 400: dict})
    def signup(self, request: UserSignupSchema):
        if User.objects.filter(username=request.username).exists():
            raise ValidationError("A user with this username already exists.")
        try:
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
        except ValidationError as e:
            return 400, {"error": e.messages}
        except Exception as e:
            return 400, {"error": str(e)}

    @http_post("/superuser", response={201: UserSchema, 400: dict})
    def create_superuser(self, request: UserSignupSchema):
        try:
            validate_password(request.password)
            if request.is_superuser and not request.is_staff:
                raise ValueError("Superuser must have is_staff=True.")
            user = User.objects.create_superuser(
                **request.dict(exclude_unset=True),
                is_staff=True,
                is_superuser=True,
            )
            return 201, UserSchema.from_orm(user)
        except ValidationError as e:
            return 400, {"error": e.messages}
        except Exception as e:
            return 400, {"error": str(e)}

    @http_get("/{user_id}", response={200: UserSchema, 404: dict})
    def get_user(self, user_id: UUID):
        user = get_object_or_404(User, id=user_id)
        return 200, UserSchema.from_orm(user)

    @http_get("/", response={200: list[UserSchema]})
    def list_users(self):
        users = User.objects.all()
        return 200, [UserSchema.from_orm(user) for user in users]

    @http_put("/{user_id}", response={200: UserSchema, 400: dict, 404: dict})
    def update_user(self, user_id: UUID, payload: UserUpdateSchema):
        user = get_object_or_404(User, id=user_id)
        for attr, value in payload.dict(exclude_unset=True).items():
            setattr(user, attr, value)
        try:
            user.save()
            return 200, UserSchema.from_orm(user)
        except Exception as e:
            return 400, {"error": str(e)}

    @http_delete("/{user_id}", response={204: None, 404: dict})
    def delete_user(self, user_id: UUID):
        try:
            user = get_object_or_404(User, id=user_id)
            user.delete()
            return 204, None
        except Exception as e:
            return 400, {"error": str(e)}

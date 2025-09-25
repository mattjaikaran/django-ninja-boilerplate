import logging
import secrets
from datetime import timedelta, timezone

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_post
from ninja_jwt.tokens import RefreshToken

from api.decorators import create_endpoint, handle_exceptions, log_api_call
from core.models import OneTimePassword
from core.schemas import (
    PasswordlessLoginRequest,
    PasswordlessLoginVerify,
    UserLoginSchema,
    UserSchema,
    UserSignupSchema,
)

User = get_user_model()

logger = logging.getLogger(__name__)


@api_controller("/auth", tags=["Auth"])
class AuthController:
    @http_post("/signup", response={201: UserSchema, 400: dict})
    @create_endpoint(require_auth=False)
    def signup(self, data: UserSignupSchema):
        """Create a new user account."""
        # Check if username exists
        if User.objects.filter(username=data.username).exists():
            validation_error = ValidationError(
                "A user with this username already exists."
            )
            raise validation_error

        # Check if email exists
        if User.objects.filter(email=data.email).exists():
            validation_error = ValidationError("A user with this email already exists.")
            raise validation_error

        # Validate password
        validate_password(data.password)

        # Create user
        user = User.objects.create_user(
            username=data.username,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            is_staff=False,
            is_superuser=False,
        )
        return 201, UserSchema.from_orm(user)

    @http_post("/login", response={200: dict, 400: dict})
    @create_endpoint(require_auth=False)
    def login(self, data: UserLoginSchema):
        """Authenticate user and return tokens."""
        user = authenticate(username=data.username, password=data.password)
        if not user:
            validation_error = ValidationError("Invalid credentials")
            raise validation_error

        # Generate token

        refresh = RefreshToken.for_user(user)
        return 200, {
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSchema.from_orm(user).dict(),
        }

    @http_post("/passwordless/login/request", response={200: dict})
    @handle_exceptions
    @log_api_call()
    def request_passwordless_login(self, payload: PasswordlessLoginRequest):
        """Request passwordless login magic link."""
        email = payload.email.lower()
        user_exists = User.objects.filter(email=email).exists()

        if user_exists:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            expires_at = timezone.now() + timedelta(minutes=15)

            OneTimePassword.objects.create(
                user=user, token=token, expires_at=expires_at
            )

            magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"

            # Use the email service if available, fallback to send_mail
            try:
                from core.services.email.service import EmailService

                email_service = EmailService()
                email_service.send_simple_email(
                    subject="Your Magic Link",
                    message=f"Click to login: {magic_link}",
                    recipient_email=email,
                )
            except ImportError:
                from django.core.mail import send_mail

                send_mail(
                    subject="Your Magic Link",
                    message=f"Click to login: {magic_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )

        # Always return success for security (prevent email enumeration)
        return 200, {"detail": "If registered, you'll receive a magic link"}

    @http_post("/passwordless/login/verify", response={200: dict})
    @handle_exceptions
    @log_api_call()
    def verify_passwordless_login(self, payload: PasswordlessLoginVerify):
        """Verify passwordless login token and return JWT tokens."""
        otp = get_object_or_404(
            OneTimePassword.objects.select_related("user"),
            token=payload.token,
            is_used=False,
            expires_at__gte=timezone.now(),
        )

        otp.is_used = True
        otp.save()

        refresh = RefreshToken.for_user(otp.user)
        return 200, {"access": str(refresh.access_token), "refresh": str(refresh)}

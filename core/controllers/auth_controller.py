"""Authentication controller for user authentication and session management.

This module provides API endpoints for user signup, login (email and username),
passwordless authentication via magic links, and token refresh.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja_extra import api_controller, http_get, http_post
from ninja_jwt.tokens import RefreshToken

from api.decorators import handle_exceptions, log_api_call
from core.models import OneTimePassword
from core.schemas import (
    AuthStatusSchema,
    LoginSchema,
    MessageResponse,
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
    """Authentication controller for user auth operations."""

    @http_post("/signup", response={201: UserSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def signup(self, data: UserSignupSchema):
        """Create a new user account.

        Creates a new user with the provided credentials and profile information.
        Returns the created user data on success.
        """
        # Check if username exists
        if User.objects.filter(username=data.username).exists():
            validation_error = ValidationError(
                "A user with this username already exists."
            )
            raise validation_error

        # Check if email exists
        if User.objects.filter(email=data.email.lower()).exists():
            validation_error = ValidationError("A user with this email already exists.")
            raise validation_error

        # Validate password
        validate_password(data.password)

        # Create user
        user = User.objects.create_user(
            username=data.username,
            email=data.email.lower(),
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            is_staff=False,
            is_superuser=False,
        )

        logger.info("Created new user: %s", user.email)
        return 201, UserSchema.from_orm(user)

    @http_post("/login", response={200: dict, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def login(self, data: LoginSchema):
        """Authenticate user with email and password.

        Returns JWT access and refresh tokens along with user data.
        This is the preferred login method using email.
        """
        # Try to authenticate with email
        try:
            user_obj = User.objects.get(email=data.email.lower())
            user = authenticate(username=user_obj.username, password=data.password)
        except User.DoesNotExist:
            user = None

        if not user:
            validation_error = ValidationError("Invalid credentials")
            raise validation_error

        if not user.is_active:
            validation_error = ValidationError("Account is disabled")
            raise validation_error

        # Update last login
        user.save(update_fields=["last_login"])

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        logger.info("User logged in: %s", user.email)

        return 200, {
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSchema.from_orm(user).dict(),
        }

    @http_post("/login/username", response={200: dict, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def login_username(self, data: UserLoginSchema):
        """Authenticate user with username and password (legacy).

        Returns JWT access and refresh tokens along with user data.
        Use /login endpoint with email for new implementations.
        """
        user = authenticate(username=data.username, password=data.password)

        if not user:
            validation_error = ValidationError("Invalid credentials")
            raise validation_error

        if not user.is_active:
            validation_error = ValidationError("Account is disabled")
            raise validation_error

        # Update last login
        user.save(update_fields=["last_login"])

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        return 200, {
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSchema.from_orm(user).dict(),
        }

    @http_post("/logout", response={200: MessageResponse})
    @handle_exceptions()
    @log_api_call()
    def logout(self, request):
        """Logout the current user.

        Note: For stateless JWT, client should discard tokens.
        This endpoint can be used to blacklist refresh tokens if needed.
        """
        return 200, {"message": "Successfully logged out", "success": True}

    @http_get("/me", response={200: UserSchema, 401: dict})
    @handle_exceptions()
    @log_api_call()
    def get_current_user(self, request):
        """Get the currently authenticated user's profile."""
        if not request.user or not request.user.is_authenticated:
            return 401, {"error": "Not authenticated"}
        return 200, UserSchema.from_orm(request.user)

    @http_get("/status", response={200: AuthStatusSchema})
    @handle_exceptions()
    def get_auth_status(self, request):
        """Check authentication status."""
        if request.user and request.user.is_authenticated:
            return 200, {
                "authenticated": True,
                "user_id": str(request.user.id),
                "email": request.user.email,
            }
        return 200, {
            "authenticated": False,
            "user_id": None,
            "email": None,
        }

    # =========================================================================
    # Passwordless Authentication (Magic Links)
    # =========================================================================

    @http_post("/passwordless/login/request", response={200: dict})
    @handle_exceptions()
    @log_api_call()
    def request_passwordless_login(self, payload: PasswordlessLoginRequest):
        """Request passwordless login magic link.

        Sends a magic link to the user's email if the account exists.
        Always returns success to prevent email enumeration.
        """
        email = payload.email.lower()
        user_exists = User.objects.filter(email=email).exists()

        if user_exists:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            expires_at = timezone.now() + timedelta(minutes=15)

            OneTimePassword.objects.create(
                user=user,
                token=token,
                expires_at=expires_at,
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
                logger.info("Magic link sent to: %s", email)
            except ImportError:
                from django.core.mail import send_mail

                send_mail(
                    subject="Your Magic Link",
                    message=f"Click to login: {magic_link}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info("Magic link sent via send_mail to: %s", email)

        # Always return success for security (prevent email enumeration)
        return 200, {"detail": "If registered, you'll receive a magic link"}

    @http_post("/passwordless/login/verify", response={200: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def verify_passwordless_login(self, payload: PasswordlessLoginVerify):
        """Verify passwordless login token and return JWT tokens.

        Validates the magic link token and returns access/refresh tokens.
        """
        otp = get_object_or_404(
            OneTimePassword.objects.select_related("user"),
            token=payload.token,
            is_used=False,
            expires_at__gte=timezone.now(),
        )

        otp.is_used = True
        otp.save()

        # Update last login
        otp.user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(otp.user)

        logger.info("Magic link verified for: %s", otp.user.email)

        return 200, {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSchema.from_orm(otp.user).dict(),
        }

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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.throttling import DynamicRateThrottle, throttle
from core.security.cookie_auth import CookieJWTAuth
from core.security.cookie_auth import (
    RefreshCookieAuth,
    delete_auth_cookies,
    issue_auth_cookies,
    set_auth_cookies,
)
from django.middleware.csrf import get_token
from core.schemas.base_schema import CamelCaseSchema
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from api.decorators import log_api_call
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
from core.security.brute_force import (
    clear_attempts,
    is_locked_out,
    record_failed_attempt,
    remaining_attempts,
)

User = get_user_model()

logger = logging.getLogger(__name__)


class CSRFResponseSchema(CamelCaseSchema):
    csrfToken: str


@api_controller("/auth", tags=["Auth"], auth=CookieJWTAuth(), use_unique_op_id=False)
class AuthController:
    """HTTP controller for authentication and session management.

    Handles user registration, email/password login, username/password login
    (legacy), logout, current-user profile retrieval, auth-status checks, and
    passwordless magic-link login.

    Public endpoints use Django CSRF protection for unsafe requests.
        POST /auth/signup                      — create a new account
        POST /auth/login                       — email + password login
        POST /auth/login/username              — username + password login (legacy)
        POST /auth/passwordless/login/request  — request a magic link
        POST /auth/passwordless/login/verify   — verify a magic link token
        GET  /auth/csrf                        — bootstrap Django CSRF
        POST /auth/logout                      — revoke cookie session

    Protected endpoints (JWT cookies required):
        POST /auth/refresh                     — rotate the refresh cookie
        GET  /auth/me                          — current user profile
        GET  /auth/status                      — authentication status check
    """

    @http_post(
        "/signup", response={201: UserSchema, 400: dict}, auth=None, by_alias=True
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call(include_payload=True)
    def signup(self, request, payload: UserSignupSchema):
        """Create a new user account.

        Validates that neither the username nor email is already taken,
        runs Django's password validators, then creates the user. Rate
        limited to 10 requests per minute per IP.

        Args:
            request: The HTTP request object.
            payload: Validated signup data including username, email, and password.

        Returns:
            Tuple of (201, UserSchema) on success or (400, error_dict) on
            duplicate username/email or invalid password.

        Raises:
            ValidationError: If username or email is already in use, or if
                the password fails Django's password validators.
        """
        # Check if username exists
        if User.objects.filter(username=payload.username).exists():
            validation_error = ValidationError(
                "A user with this username already exists."
            )
            raise validation_error

        # Check if email exists
        if User.objects.filter(email=payload.email.lower()).exists():
            validation_error = ValidationError("A user with this email already exists.")
            raise validation_error

        # Validate password
        validate_password(payload.password)

        # Create user
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username=payload.username,
            email=payload.email.lower(),
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            is_staff=False,
            is_superuser=False,
        )

        logger.info("Created new user: %s", user.email)
        return 201, UserSchema.model_validate(user)

    @http_get("/csrf", response=CSRFResponseSchema, auth=None)
    def csrf(self, request):
        return {"csrfToken": get_token(request)}

    @http_post(
        "/login",
        response={200: UserSchema, 400: dict, 429: dict},
        auth=None,
        by_alias=True,
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call(include_payload=True)
    def login(self, request, response: HttpResponse, payload: LoginSchema):
        """Authenticate a user with email and password.

        Looks up the user by email, delegates to Django's ``authenticate``
        (which verifies the password), checks the account is active, then
        issues HttpOnly access/refresh cookies.

        Args:
            request: The HTTP request object.
            payload: Validated login data with ``email`` and ``password`` fields.

        Returns:
            UserSchema on success, or an error on invalid credentials.

        Raises:
            ValidationError: If credentials are invalid or the account is
                disabled.
        """
        lockout_key = f"login:email:{payload.email.lower()}"
        if is_locked_out(lockout_key):
            return 429, {
                "error": "Account temporarily locked due to too many failed attempts. Try again in 15 minutes."
            }

        # USERNAME_FIELD is email, so Django's username credential must be the email.
        user = authenticate(username=payload.email.lower(), password=payload.password)

        if not user:
            remaining = remaining_attempts(lockout_key)
            record_failed_attempt(lockout_key)
            logger.warning(
                "Failed login attempt for email: %s (%d attempts remaining)",
                payload.email.lower(),
                remaining - 1,
            )
            raise ValidationError("Invalid credentials")

        if not user.is_active:
            raise ValidationError("Account is disabled")

        clear_attempts(lockout_key)

        # Update last login
        user.save(update_fields=["last_login"])

        issue_auth_cookies(request, response, user)
        logger.info("User logged in: %s", user.email)
        return 200, UserSchema.model_validate(user)

    @http_post(
        "/login/username",
        response={200: UserSchema, 400: dict, 429: dict},
        auth=None,
        by_alias=True,
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call(include_payload=True)
    def login_username(self, request, response: HttpResponse, payload: UserLoginSchema):
        """Authenticate a user with username and password (legacy).

        Provided for backwards compatibility with clients that send a username
        instead of an email address. New implementations should use the
        ``/auth/login`` endpoint with email.

        Args:
            request: The HTTP request object.
            payload: Validated login data with ``username`` and ``password`` fields.

        Returns:
            UserSchema on success, or an error on invalid credentials.

        Raises:
            ValidationError: If credentials are invalid or the account is
                disabled.
        """
        lockout_key = f"login:username:{payload.username}"
        if is_locked_out(lockout_key):
            return 429, {
                "error": "Account temporarily locked due to too many failed attempts. Try again in 15 minutes."
            }

        user_obj = User.objects.filter(username=payload.username).first()
        user = (
            authenticate(username=user_obj.email, password=payload.password)
            if user_obj
            else None
        )

        if not user:
            record_failed_attempt(lockout_key)
            raise ValidationError("Invalid credentials")

        if not user.is_active:
            raise ValidationError("Account is disabled")

        clear_attempts(lockout_key)

        # Update last login
        user.save(update_fields=["last_login"])

        issue_auth_cookies(request, response, user)
        return 200, UserSchema.model_validate(user)

    @http_post(
        "/refresh", response={200: MessageResponse, 401: dict}, auth=RefreshCookieAuth()
    )
    def refresh(self, request, response: HttpResponse):
        """Rotate and revoke the refresh cookie without a request body."""
        request.refresh_token.blacklist()
        set_auth_cookies(response, RefreshToken.for_user(request.user))
        return 200, {"message": "Session refreshed", "success": True}

    @http_post("/logout", response={200: MessageResponse}, auth=None)
    def logout(self, request, response: HttpResponse):
        """Revoke the browser refresh cookie and clear both auth cookies."""
        try:
            RefreshToken(request.COOKIES.get("refresh_token", "")).blacklist()
        except TokenError:
            pass
        delete_auth_cookies(response)
        return 200, {"message": "Successfully logged out", "success": True}

    @http_get("/me", response={200: UserSchema, 401: dict}, by_alias=True)
    @log_api_call()
    def get_current_user(self, request):
        """Retrieve the currently authenticated user's profile.

        Args:
            request: The HTTP request object containing the JWT-authenticated user.

        Returns:
            Tuple of (200, UserSchema) on success or (401, error_dict) if the
            request is not authenticated.
        """
        if not request.user or not request.user.is_authenticated:
            return 401, {"error": "Not authenticated"}
        return 200, UserSchema.model_validate(request.user)

    @http_get("/status", response={200: AuthStatusSchema})
    def get_auth_status(self, request):
        """Check whether the current request is authenticated.

        Always returns HTTP 200. The ``authenticated`` flag in the response
        body indicates the actual state. Safe to call without a token.

        Args:
            request: The HTTP request object.

        Returns:
            Tuple of (200, AuthStatusSchema) with ``authenticated``,
            ``user_id``, and ``email`` fields.
        """
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

    @http_post("/passwordless/login/request", response={200: dict}, auth=None)
    @throttle(DynamicRateThrottle, scope="anon-email")
    @log_api_call()
    def request_passwordless_login(self, request, payload: PasswordlessLoginRequest):
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

    @http_post(
        "/passwordless/login/verify",
        response={200: UserSchema, 404: dict},
        auth=None,
        by_alias=True,
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call()
    def verify_passwordless_login(
        self, request, response: HttpResponse, payload: PasswordlessLoginVerify
    ):
        """Verify a magic link and issue HttpOnly authentication cookies."""
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

        issue_auth_cookies(request, response, otp.user)
        logger.info("Magic link verified for: %s", otp.user.email)
        return 200, UserSchema.model_validate(otp.user)

"""Authentication controller for user authentication.

This module provides API endpoints for user signup, login (email and username),
and passwordless authentication via magic links. Logins set the httpOnly auth
cookies in ``docs/COOKIE_AUTH.md``; bearer clients read the tokens from the
body.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.throttling import DynamicRateThrottle, throttle
from ninja_jwt.authentication import JWTAuth

from api.decorators import log_api_call
from core.models import OneTimePassword
from core.schemas import (
    AuthStatusSchema,
    LoginSchema,
    MessageResponse,
    PasswordlessLoginRequest,
    PasswordlessLoginVerify,
    PasswordlessTokenSchema,
    TokenSchema,
    UserLoginSchema,
    UserSchema,
    UserSignupSchema,
)
from core.security.brute_force import (
    LOCKOUT_MESSAGE,
    clear_login_failures,
    is_login_locked,
    record_login_failure,
)
from core.security.cookie_auth import issue_token_pair, set_auth_cookies
from core.services.email.service import send_account_email

User = get_user_model()

logger = logging.getLogger(__name__)

# Every signup gets this answer, whether or not the account exists.
SIGNUP_ACCEPTED_MESSAGE = "Check your email to finish signing up."


class CSRFResponseSchema(CamelCaseSchema):
    csrfToken: str


@api_controller("/auth", tags=["Auth"], auth=CookieJWTAuth(), use_unique_op_id=False)
class AuthController:
    """HTTP controller for authentication.

    Handles user registration, email/password login, username/password login
    (legacy), current-user profile retrieval, auth-status checks, and
    passwordless magic-link login. Login endpoints also set the httpOnly auth
    cookies; CSRF, refresh, and logout live in ``SessionController``.

    Public endpoints use Django CSRF protection for unsafe requests.
        POST /auth/signup                      — create a new account
        POST /auth/login                       — email + password login
        POST /auth/login/username              — username + password login (legacy)
        POST /auth/passwordless/login/request  — request a magic link
        POST /auth/passwordless/login/verify   — verify a magic link token
        GET  /auth/csrf                        — bootstrap Django CSRF
        POST /auth/logout                      — revoke cookie session

    Protected endpoints (JWT required):
        GET  /auth/me                          — current user profile
        GET  /auth/status                      — authentication status check
    """

    @http_post("/signup", response={202: MessageResponse, 400: dict}, auth=None)
    @throttle(DynamicRateThrottle, scope="anon-email")
    @log_api_call(include_payload=True)
    def signup(self, request, payload: UserSignupSchema):
        """Start account creation without revealing which accounts exist.

        Runs Django's password validators, then always answers 202 with the
        same message. A new email and username create the account and send a
        welcome email. A taken email sends its owner a notice instead; a taken
        username sends the address a "choose another username" email. Every
        path hashes the password and sends one email off the request, so
        status, body and timing match.

        Args:
            request: The HTTP request object.
            payload: Validated signup data including username, email, and password.

        Returns:
            Tuple of (202, MessageResponse), or (400, error_dict) when the
            password fails validation (depends on the input only).
        """
        email = payload.email.lower()
        candidate = User(
            username=payload.username,
            email=email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        validate_password(payload.password, candidate)

        login_url = f"{settings.FRONTEND_URL}/login"
        if User.objects.filter(email=email).exists():
            make_password(payload.password)  # same hashing cost as create_user
            subject = "Sign-up attempt for your account"
            body = (
                "Someone tried to create an account with this email address. "
                f"If it was you, sign in at {login_url} or reset your password. "
                "If not, you can ignore this email."
            )
        elif User.objects.filter(username=payload.username).exists():
            make_password(payload.password)
            subject = "Finish signing up"
            body = (
                "The username you chose is taken, so no account was created. "
                f"Sign up again with another username at {settings.FRONTEND_URL}."
            )
        else:
            try:
                with transaction.atomic():
                    User.objects.create_user(  # type: ignore[attr-defined]
                        username=payload.username,
                        email=email,
                        password=payload.password,
                        first_name=payload.first_name,
                        last_name=payload.last_name,
                        is_staff=False,
                        is_superuser=False,
                    )
            except (ValidationError, IntegrityError):
                # Lost a race with a concurrent signup; answer the same way.
                logger.info("Signup raced with an existing account")
                return 202, MessageResponse(message=SIGNUP_ACCEPTED_MESSAGE)
            subject = "Welcome"
            body = f"Your account is ready. Sign in at {login_url}."

        send_account_email(subject, body, email)
        return 202, MessageResponse(message=SIGNUP_ACCEPTED_MESSAGE)

    @http_post("/login", response={200: TokenSchema, 400: dict, 429: dict}, auth=None)
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call(include_payload=True)
    def login(self, request, response: HttpResponse, payload: LoginSchema):
        """Authenticate a user with email and password.

        Looks up the user by email, delegates to Django's ``authenticate``
        (which verifies the password and rejects inactive accounts), then
        issues a JWT access/refresh token pair. Failures count against the
        account and the client IP (``core.security.brute_force``).

        Args:
            request: The HTTP request object.
            response: Temporal response that carries the auth cookies.
            payload: Validated login data with ``email`` and ``password`` fields.

        Returns:
            Tuple of (200, TokenSchema) containing ``token``, ``refresh``, and
            ``user`` keys on success, (400, error_dict) on invalid
            credentials, or (429, error_dict) while the account or IP is
            locked out. Also sets the httpOnly auth cookies.

        Raises:
            ValidationError: If credentials are invalid.
        """
        account = f"email:{payload.email.lower()}"
        if is_login_locked(account, request):
            return 429, {"error": LOCKOUT_MESSAGE}

        # USERNAME_FIELD is email, so Django's username credential must be the email.
        user = authenticate(username=payload.email.lower(), password=payload.password)

        if not user:
            record_login_failure(account, request)
            raise ValidationError("Invalid credentials")

        clear_login_failures(account, request)
        return 200, self._issue_tokens(user, response)

    @http_post(
        "/login/username", response={200: TokenSchema, 400: dict, 429: dict}, auth=None
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call(include_payload=True)
    def login_username(self, request, response: HttpResponse, payload: UserLoginSchema):
        """Authenticate a user with username and password (legacy).

        Provided for backwards compatibility with clients that send a username
        instead of an email address. New implementations should use the
        ``/auth/login`` endpoint with email. An unknown username still hashes
        the password, so timing does not reveal which usernames exist.

        Args:
            request: The HTTP request object.
            response: Temporal response that carries the auth cookies.
            payload: Validated login data with ``username`` and ``password`` fields.

        Returns:
            Tuple of (200, TokenSchema) containing ``token``, ``refresh``, and
            ``user`` keys on success, (400, error_dict) on invalid
            credentials, or (429, error_dict) while the account or IP is
            locked out. Also sets the httpOnly auth cookies.

        Raises:
            ValidationError: If credentials are invalid.
        """
        user_obj = User.objects.filter(username=payload.username).first()
        # A known username counts against the same email key as /auth/login,
        # /api/token/pair and the admin form, so switching endpoints does not
        # add guesses.
        account = (
            f"email:{user_obj.email.lower()}"
            if user_obj
            else f"username:{payload.username}"
        )
        if is_login_locked(account, request):
            return 429, {"error": LOCKOUT_MESSAGE}

        if user_obj:
            user = authenticate(username=user_obj.email, password=payload.password)
        else:
            make_password(payload.password)  # same hashing cost as a real check
            user = None

        if not user:
            record_login_failure(account, request)
            raise ValidationError("Invalid credentials")

        clear_login_failures(account, request)
        return 200, self._issue_tokens(user, response)

    @staticmethod
    def _issue_tokens(user, response: HttpResponse) -> TokenSchema:
        """Record the login, set the auth cookies and return the token pair."""
        user.save(update_fields=["last_login"])
        access, refresh = issue_token_pair(user)
        set_auth_cookies(response, access, refresh)
        # Log the id, not the email: logs must not carry PII.
        logger.info("User logged in: %s", user.pk)
        return TokenSchema(
            token=access, refresh=refresh, user=UserSchema.model_validate(user)
        )

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
        user = User.objects.filter(email=email, is_active=True).first()

        if user:
            token = secrets.token_urlsafe(32)
            OneTimePassword.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timedelta(minutes=15),
            )
            magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
            # Sent off the request: delivery time must not reveal the account.
            send_account_email(
                "Your Magic Link", f"Click to login: {magic_link}", email
            )

        # Same answer for every address (prevents email enumeration).
        return 200, {"detail": "If registered, you'll receive a magic link"}

    @http_post(
        "/passwordless/login/verify",
        response={200: PasswordlessTokenSchema, 404: dict},
        auth=None,
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    @log_api_call()
    def verify_passwordless_login(
        self, request, response: HttpResponse, payload: PasswordlessLoginVerify
    ):
        """Verify passwordless login token and return JWT tokens.

        Validates the magic link token, returns access/refresh tokens, and sets
        the httpOnly auth cookies.
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

        access, refresh = issue_token_pair(otp.user)
        set_auth_cookies(response, access, refresh)

        logger.info("Magic link verified for: %s", otp.user.email)

        return 200, PasswordlessTokenSchema(
            access=access, refresh=refresh, user=UserSchema.model_validate(otp.user)
        )

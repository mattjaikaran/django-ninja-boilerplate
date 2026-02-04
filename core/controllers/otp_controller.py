"""OTP controller for mobile/iOS authentication.

This module provides API endpoints for:
- Requesting OTP codes (6-digit) for mobile apps
- Verifying OTP codes
- Password reset via OTP
- Email verification via OTP
- Two-factor authentication
"""

import logging

from django.contrib.auth import get_user_model
from ninja_extra import api_controller, http_post
from ninja_jwt.tokens import RefreshToken

from api.decorators import handle_exceptions, log_api_call
from api.utils.http import get_client_ip, get_user_agent
from core.schemas import MessageResponse, UserSchema
from core.schemas.otp_schema import (
    OTPRequestSchema,
    OTPResponseSchema,
    OTPTokenVerifySchema,
    OTPVerifyResponseSchema,
    OTPVerifySchema,
    PasswordResetWithOTPSchema,
    ResendOTPSchema,
    SignupWithOTPSchema,
    TwoFactorSetupSchema,
    TwoFactorVerifySchema,
)
from core.services.otp_service import otp_service

User = get_user_model()
logger = logging.getLogger(__name__)


@api_controller("/auth/otp", tags=["OTP Authentication"])
class OTPController:
    """OTP authentication controller for mobile/iOS apps.

    Provides 6-digit OTP code authentication suitable for mobile apps,
    iOS, Android, and other native applications.
    """

    @http_post("/request", response={200: OTPResponseSchema, 400: dict, 429: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def request_otp(self, request, payload: OTPRequestSchema):
        """Request a 6-digit OTP code.

        Sends an OTP code to the user's email or phone for authentication.
        Rate limited to prevent abuse.

        **Purposes:**
        - `LOGIN`: Login with OTP instead of password
        - `SIGNUP_VERIFICATION`: Verify email after registration
        - `PASSWORD_RESET`: Reset forgotten password
        - `EMAIL_CHANGE`: Verify new email address
        - `PHONE_VERIFICATION`: Verify phone number
        - `TWO_FACTOR`: Two-factor authentication

        **Delivery Methods:**
        - `EMAIL`: Send code via email
        - `SMS`: Send code via SMS (requires SMS provider integration)
        - `PUSH`: Send code via push notification (requires push integration)
        """
        success, message, expires_in = otp_service.request_otp(
            email=payload.email,
            phone=payload.phone,
            purpose=payload.purpose,
            delivery_method=payload.delivery_method,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        if not success:
            if "Rate limit" in message or "Too many" in message:
                return 429, {"error": message, "success": False}
            return 400, {"error": message, "success": False}

        return 200, OTPResponseSchema(
            success=True,
            message=message,
            expires_in_seconds=expires_in,
        )

    @http_post("/verify", response={200: OTPVerifyResponseSchema, 400: dict, 401: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def verify_otp(self, request, payload: OTPVerifySchema):
        """Verify a 6-digit OTP code.

        Validates the OTP code and returns authentication tokens on success.
        Can be used for login, password reset confirmation, or other purposes.

        Returns JWT access and refresh tokens along with user data.
        """
        success, message, user = otp_service.verify_otp(
            email=payload.email,
            phone=payload.phone,
            code=payload.code,
            purpose=payload.purpose,
        )

        if not success or not user:
            return 401, {"error": message, "success": False}

        # Generate tokens for LOGIN purpose
        if payload.purpose == "LOGIN":
            refresh = RefreshToken.for_user(user)

            logger.info("User logged in via OTP: %s", user.email)

            return 200, OTPVerifyResponseSchema(
                success=True,
                message="Login successful",
                access=str(refresh.access_token),
                refresh=str(refresh),
                user=UserSchema.from_orm(user).dict(),
            )

        # For other purposes, just return success
        return 200, OTPVerifyResponseSchema(
            success=True,
            message=message,
        )

    @http_post(
        "/verify-token", response={200: OTPVerifyResponseSchema, 400: dict, 401: dict}
    )
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def verify_token(self, request, payload: OTPTokenVerifySchema):
        """Verify a magic link token.

        Used for passwordless authentication via email magic links.
        Returns JWT access and refresh tokens along with user data.
        """
        success, message, user = otp_service.verify_token(token=payload.token)

        if not success or not user:
            return 401, {"error": message, "success": False}

        refresh = RefreshToken.for_user(user)

        logger.info("User logged in via magic link: %s", user.email)

        return 200, OTPVerifyResponseSchema(
            success=True,
            message="Login successful",
            access=str(refresh.access_token),
            refresh=str(refresh),
            user=UserSchema.from_orm(user).dict(),
        )

    @http_post("/resend", response={200: OTPResponseSchema, 400: dict, 429: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def resend_otp(self, request, payload: ResendOTPSchema):
        """Resend an OTP code.

        Generates and sends a new OTP code, invalidating any previous codes.
        Subject to rate limiting.
        """
        success, message, expires_in = otp_service.request_otp(
            email=payload.email,
            phone=payload.phone,
            purpose=payload.purpose,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        if not success:
            if "Rate limit" in message or "Too many" in message:
                return 429, {"error": message, "success": False}
            return 400, {"error": message, "success": False}

        return 200, OTPResponseSchema(
            success=True,
            message="New code sent",
            expires_in_seconds=expires_in,
        )

    @http_post("/password-reset/request", response={200: MessageResponse, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def request_password_reset(self, request, payload: OTPRequestSchema):
        """Request password reset via OTP.

        Sends a 6-digit code to reset the password.
        Always returns success to prevent email enumeration.
        """
        success, message = otp_service.request_password_reset(
            email=payload.email,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        # Always return success to prevent email enumeration
        return 200, MessageResponse(
            message="If an account exists, you will receive a password reset code",
            success=True,
        )

    @http_post(
        "/password-reset/confirm", response={200: MessageResponse, 400: dict, 401: dict}
    )
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def confirm_password_reset(self, request, payload: PasswordResetWithOTPSchema):
        """Confirm password reset with OTP code.

        Verifies the OTP code and sets the new password.
        """
        success, message = otp_service.reset_password_with_otp(
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
        )

        if not success:
            return 401, {"error": message, "success": False}

        return 200, MessageResponse(
            message="Password reset successfully",
            success=True,
        )

    @http_post("/email/verify", response={200: MessageResponse, 400: dict, 401: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def verify_email(self, request, payload: SignupWithOTPSchema):
        """Verify email address with OTP code.

        Used after signup to verify the user's email address.
        """
        success, message = otp_service.verify_email(
            email=payload.email,
            code=payload.code,
        )

        if not success:
            return 401, {"error": message, "success": False}

        return 200, MessageResponse(
            message="Email verified successfully",
            success=True,
        )

    @http_post(
        "/2fa/request",
        response={200: OTPResponseSchema, 400: dict, 401: dict, 429: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def request_two_factor(self, request, payload: TwoFactorSetupSchema):
        """Request a two-factor authentication code.

        Sends a 2FA code to the authenticated user.
        Requires authentication.
        """
        if not request.user or not request.user.is_authenticated:
            return 401, {"error": "Authentication required", "success": False}

        success, message, expires_in = otp_service.request_two_factor(
            user=request.user,
            delivery_method=payload.delivery_method,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        if not success:
            if "Rate limit" in message or "Too many" in message:
                return 429, {"error": message, "success": False}
            return 400, {"error": message, "success": False}

        return 200, OTPResponseSchema(
            success=True,
            message=message,
            expires_in_seconds=expires_in,
        )

    @http_post("/2fa/verify", response={200: MessageResponse, 400: dict, 401: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def verify_two_factor(self, request, payload: TwoFactorVerifySchema):
        """Verify a two-factor authentication code.

        Validates the 2FA code for the authenticated user.
        Requires authentication.
        """
        if not request.user or not request.user.is_authenticated:
            return 401, {"error": "Authentication required", "success": False}

        success, message = otp_service.verify_two_factor(
            user=request.user,
            code=payload.code,
        )

        if not success:
            return 401, {"error": message, "success": False}

        # Optionally remember device
        if payload.remember_device:
            # In production, store a device token/fingerprint
            logger.info("Device remembered for user %s", request.user.email)

        return 200, MessageResponse(
            message="Two-factor authentication successful",
            success=True,
        )

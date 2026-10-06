"""OTP service for handling one-time password operations.

This module provides business logic for:
- Generating and sending OTP codes
- Verifying OTP codes and tokens
- Rate limiting OTP requests
- Cleanup of expired OTPs
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from core.models.otp import OneTimePassword, OTPDeliveryMethod, OTPPurpose, OTPRateLimit
from core.services.email.service import send_account_email

if TYPE_CHECKING:
    from core.models import User


def _get_user_model():
    from django.contrib.auth import get_user_model

    return get_user_model()


logger = logging.getLogger(__name__)


class OTPService:
    """Service class for OTP operations.

    Handles the business logic for generating, sending, and verifying
    one-time passwords for various authentication purposes.
    """

    # Configuration
    DEFAULT_EXPIRY_MINUTES = 10
    MAGIC_LINK_EXPIRY_MINUTES = 15
    PASSWORD_RESET_EXPIRY_MINUTES = 30
    MAX_ATTEMPTS = 5
    RATE_LIMIT_REQUESTS = 5
    RATE_LIMIT_WINDOW_MINUTES = 15
    RATE_LIMIT_BLOCK_MINUTES = 60
    NEUTRAL_REQUEST_MESSAGE = "If an account exists, you will receive an OTP code"

    def __init__(self):
        """Initialize the OTP service."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def request_otp(
        self,
        email: str | None = None,
        phone: str | None = None,
        purpose: str = OTPPurpose.LOGIN.value,
        delivery_method: str = OTPDeliveryMethod.EMAIL.value,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[bool, str, int | None]:
        """Request a new OTP code.

        Args:
            email: User's email address
            phone: User's phone number
            purpose: Purpose of the OTP
            delivery_method: How to deliver the OTP
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            tuple: (success, message, expires_in_seconds)
        """
        # Normalise so case variants of one address share one rate-limit bucket.
        identifier = (email or "").strip().lower() or phone
        if not identifier:
            return False, "Email or phone is required", None

        # Check rate limit
        is_allowed, error_message = OTPRateLimit.check_rate_limit(
            identifier=identifier,
            purpose=purpose,
            max_requests=self.RATE_LIMIT_REQUESTS,
            window_minutes=self.RATE_LIMIT_WINDOW_MINUTES,
            block_minutes=self.RATE_LIMIT_BLOCK_MINUTES,
        )

        if not is_allowed:
            return False, error_message or "", None

        # Find user
        user = self._find_user(email=email, phone=phone)

        # Get expiry time based on purpose
        expiry_minutes = self._get_expiry_minutes(purpose)

        # Account-existence-sensitive purposes answer the same way for known
        # and unknown addresses. Login and reset need an account; signup
        # verification must not reach an existing one.
        neutral_purposes = [
            OTPPurpose.LOGIN.value,
            OTPPurpose.PASSWORD_RESET.value,
            OTPPurpose.SIGNUP_VERIFICATION.value,
        ]
        if purpose in [OTPPurpose.LOGIN.value, OTPPurpose.PASSWORD_RESET.value]:
            if not user:
                return True, self.NEUTRAL_REQUEST_MESSAGE, expiry_minutes * 60

        if purpose == OTPPurpose.SIGNUP_VERIFICATION.value and user:
            return True, self.NEUTRAL_REQUEST_MESSAGE, expiry_minutes * 60

        # Create OTP
        use_code = delivery_method in [
            OTPDeliveryMethod.SMS.value,
            OTPDeliveryMethod.EMAIL.value,
            OTPDeliveryMethod.PUSH.value,
        ]

        if user:
            otp = OneTimePassword.create_for_user(
                user=user,
                purpose=OTPPurpose(purpose),
                delivery_method=OTPDeliveryMethod(delivery_method),
                expires_in_minutes=expiry_minutes,
                ip_address=ip_address,
                user_agent=user_agent,
                use_code=use_code,
                max_attempts=self.MAX_ATTEMPTS,
            )

            # Send OTP
            self._send_otp(otp, delivery_method)

            self.logger.info(
                "OTP requested for user id %s, purpose: %s, method: %s",
                user.pk,
                purpose,
                delivery_method,
            )

        if purpose in neutral_purposes:
            return True, self.NEUTRAL_REQUEST_MESSAGE, expiry_minutes * 60
        return True, "OTP sent successfully", expiry_minutes * 60

    def verify_otp(
        self,
        email: str | None = None,
        phone: str | None = None,
        code: str | None = None,
        purpose: str = OTPPurpose.LOGIN.value,
    ) -> tuple[bool, str, User | None]:
        """Verify an OTP code.

        Args:
            email: User's email address
            phone: User's phone number
            code: The OTP code to verify
            purpose: Purpose of the OTP

        Returns:
            tuple: (success, message, user)
        """
        if not code:
            return False, "Code is required", None

        identifier = email or phone
        if not identifier:
            return False, "Email or phone is required", None

        user = self._find_user(email=email, phone=phone)
        if not user:
            return False, "Invalid or expired code", None

        # Find the OTP
        otp = (
            OneTimePassword.objects.filter(
                user=user,
                purpose=purpose,
                is_used=False,
                expires_at__gte=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )

        # One message for every failure: distinct messages reveal whether an
        # account (and a pending code) exists.
        if otp and otp.verify_code(code):
            self.logger.info(
                "OTP verified for user %s, purpose: %s",
                user.email,
                purpose,
            )

            # For signup verification, mark user as verified
            if purpose == OTPPurpose.SIGNUP_VERIFICATION.value:
                user.is_verified = True
                user.save(update_fields=["is_verified"])

            return True, "Code verified successfully", user

        return False, "Invalid or expired code", None

    def verify_token(
        self,
        token: str,
    ) -> tuple[bool, str, User | None]:
        """Verify an OTP token (magic link).

        Args:
            token: The token to verify

        Returns:
            tuple: (success, message, user)
        """
        if not token:
            return False, "Token is required", None

        otp = (
            OneTimePassword.objects.filter(
                token=token,
                is_used=False,
                expires_at__gte=timezone.now(),
            )
            .select_related("user")
            .first()
        )

        if not otp:
            return False, "Invalid or expired token", None

        if not otp.is_valid:
            if otp.is_expired:
                return False, "Token has expired", None
            return False, "Token is no longer valid", None

        if otp.verify_token(token):
            self.logger.info(
                "Magic link verified for user %s, purpose: %s",
                otp.user.email,
                otp.purpose,
            )
            return True, "Token verified successfully", otp.user

        return False, "Invalid token", None

    def request_password_reset(
        self,
        email: str,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[bool, str]:
        """Request a password reset OTP.

        Args:
            email: User's email address
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            tuple: (success, message)
        """
        success, message, _ = self.request_otp(
            email=email,
            purpose=OTPPurpose.PASSWORD_RESET.value,
            delivery_method=OTPDeliveryMethod.EMAIL.value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return success, message

    def reset_password_with_otp(
        self,
        email: str,
        code: str,
        new_password: str,
    ) -> tuple[bool, str]:
        """Reset password using OTP code.

        Args:
            email: User's email address
            code: The OTP code
            new_password: The new password

        Returns:
            tuple: (success, message)
        """
        success, message, user = self.verify_otp(
            email=email,
            code=code,
            purpose=OTPPurpose.PASSWORD_RESET.value,
        )

        if not success or not user:
            return False, message

        # Validate and set new password
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return False, " ".join(e.messages)

        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Log the id, not the email: logs must not carry PII. No secret logged.
        # nosemgrep: python.lang.security.audit.logging.python-logger-credential-disclosure
        self.logger.info("Password reset for user id %s", user.pk)

        return True, "Password reset successfully"

    def request_email_verification(
        self,
        email: str,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[bool, str]:
        """Request email verification OTP.

        Args:
            email: User's email address
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            tuple: (success, message)
        """
        success, message, _ = self.request_otp(
            email=email,
            purpose=OTPPurpose.SIGNUP_VERIFICATION.value,
            delivery_method=OTPDeliveryMethod.EMAIL.value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return success, message

    def verify_email(
        self,
        email: str,
        code: str,
    ) -> tuple[bool, str]:
        """Verify email using OTP code.

        Args:
            email: User's email address
            code: The OTP code

        Returns:
            tuple: (success, message)
        """
        success, message, user = self.verify_otp(
            email=email,
            code=code,
            purpose=OTPPurpose.SIGNUP_VERIFICATION.value,
        )
        return success, message

    def request_two_factor(
        self,
        user: User,
        delivery_method: str = OTPDeliveryMethod.EMAIL.value,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[bool, str, int | None]:
        """Request a two-factor authentication OTP.

        Args:
            user: The user requesting 2FA
            delivery_method: How to deliver the OTP
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            tuple: (success, message, expires_in_seconds)
        """
        # Check rate limit
        is_allowed, error_message = OTPRateLimit.check_rate_limit(
            identifier=str(user.id),
            purpose=OTPPurpose.TWO_FACTOR.value,
            max_requests=self.RATE_LIMIT_REQUESTS,
            window_minutes=self.RATE_LIMIT_WINDOW_MINUTES,
            block_minutes=self.RATE_LIMIT_BLOCK_MINUTES,
        )

        if not is_allowed:
            return False, error_message or "", None

        otp = OneTimePassword.create_for_user(
            user=user,
            purpose=OTPPurpose.TWO_FACTOR,
            delivery_method=OTPDeliveryMethod(delivery_method),
            expires_in_minutes=5,  # Short expiry for 2FA
            ip_address=ip_address,
            user_agent=user_agent,
            use_code=True,
            max_attempts=3,  # Fewer attempts for 2FA
        )

        self._send_otp(otp, delivery_method)

        return True, "Two-factor code sent", 5 * 60

    def verify_two_factor(
        self,
        user: User,
        code: str,
    ) -> tuple[bool, str]:
        """Verify a two-factor authentication code.

        Args:
            user: The user to verify
            code: The 2FA code

        Returns:
            tuple: (success, message)
        """
        success, message, _ = self.verify_otp(
            email=user.email,
            code=code,
            purpose=OTPPurpose.TWO_FACTOR.value,
        )
        return success, message

    def cleanup_expired_otps(self) -> int:
        """Clean up expired and used OTPs.

        Returns:
            int: Number of OTPs deleted
        """
        cutoff = timezone.now() - timedelta(days=7)
        deleted, _ = OneTimePassword.objects.filter(
            created_at__lt=cutoff,
        ).delete()

        # Also cleanup rate limits
        OTPRateLimit.cleanup_expired()

        self.logger.info("Cleaned up %d expired OTPs", deleted)
        return deleted

    def _find_user(
        self,
        email: str | None = None,
        phone: str | None = None,
    ) -> User | None:
        """Find a user by email or phone.

        Args:
            email: Email to search by
            phone: Phone to search by

        Returns:
            User or None
        """
        UserModel = _get_user_model()
        if email:
            try:
                return UserModel.objects.get(email=email.lower())  # type: ignore[return-value]
            except UserModel.DoesNotExist:
                return None

        if phone:
            try:
                return UserModel.objects.get(phone=phone)  # type: ignore[return-value]
            except UserModel.DoesNotExist:
                return None

        return None

    def _get_expiry_minutes(self, purpose: str) -> int:
        """Get the expiry time for a given purpose.

        Args:
            purpose: The OTP purpose

        Returns:
            int: Expiry time in minutes
        """
        if purpose == OTPPurpose.PASSWORD_RESET.value:
            return self.PASSWORD_RESET_EXPIRY_MINUTES
        if purpose == OTPPurpose.MAGIC_LINK.value:
            return self.MAGIC_LINK_EXPIRY_MINUTES
        return self.DEFAULT_EXPIRY_MINUTES

    def _send_otp(
        self,
        otp: OneTimePassword,
        delivery_method: str,
    ) -> None:
        """Send the OTP via the specified delivery method.

        Args:
            otp: The OTP to send
            delivery_method: How to send it
        """
        if delivery_method == OTPDeliveryMethod.EMAIL.value:
            self._send_otp_email(otp)
        elif delivery_method == OTPDeliveryMethod.SMS.value:
            self._send_otp_sms(otp)
        elif delivery_method == OTPDeliveryMethod.PUSH.value:
            self._send_otp_push(otp)

    def _send_otp_email(self, otp: OneTimePassword) -> None:
        """Send OTP via email.

        Args:
            otp: The OTP to send
        """
        subject_map = {
            OTPPurpose.LOGIN.value: "Your Login Code",
            OTPPurpose.SIGNUP_VERIFICATION.value: "Verify Your Email",
            OTPPurpose.PASSWORD_RESET.value: "Reset Your Password",
            OTPPurpose.EMAIL_CHANGE.value: "Verify Your New Email",
            OTPPurpose.TWO_FACTOR.value: "Your Two-Factor Code",
        }

        subject = subject_map.get(otp.purpose, "Your Verification Code")
        message = f"""
Your verification code is: {otp.code}

This code will expire in {otp.time_until_expiry.seconds // 60} minutes.

If you didn't request this code, please ignore this email.
"""

        # Off the request, so delivery time does not reveal whether the
        # account exists (unknown accounts send nothing).
        send_account_email(subject, message, otp.user.email)
        self.logger.info("OTP email queued for user id %s", otp.user.pk)

    def _send_otp_sms(self, otp: OneTimePassword) -> None:
        """Send OTP via SMS.

        Args:
            otp: The OTP to send

        Note:
            This is a placeholder. Integrate with your SMS provider
            (Twilio, Vonage, AWS SNS, etc.)
        """
        # Placeholder for SMS integration
        # In production, integrate with Twilio, Vonage, AWS SNS, etc.
        # Never log otp.code: the delivery method is client-chosen, so a logged
        # code would let anyone with log access take over any account.
        self.logger.info(
            "SMS OTP not sent (no SMS provider configured) for user %s",
            otp.user_id,
        )

    def _send_otp_push(self, otp: OneTimePassword) -> None:
        """Send OTP via push notification.

        Args:
            otp: The OTP to send

        Note:
            This is a placeholder. Integrate with your push provider
            (Firebase, OneSignal, Pusher, etc.)
        """
        # Placeholder for push notification integration
        # In production, integrate with Firebase, OneSignal, Pusher, etc.
        # Never log otp.code (see _send_otp_sms).
        self.logger.info(
            "Push OTP not sent (no push provider configured) for user %s",
            otp.user_id,
        )


# Singleton instance
otp_service = OTPService()

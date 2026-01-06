"""Celery tasks for the core application.

This module provides background tasks for:
- OTP cleanup
- User maintenance
- Periodic health checks
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="core.cleanup_expired_otps")
def cleanup_expired_otps():
    """Clean up expired and used OTP codes.

    This task should run periodically (e.g., every hour) to remove
    old OTP records and rate limit entries.

    Returns:
        dict: Statistics about cleaned records
    """
    from core.models import OneTimePassword
    from core.models.otp import OTPRateLimit

    try:
        # Delete OTPs older than 7 days
        cutoff = timezone.now() - timezone.timedelta(days=7)
        otp_deleted, _ = OneTimePassword.objects.filter(
            created_at__lt=cutoff,
        ).delete()

        # Clean up rate limits older than 24 hours
        rate_limit_deleted = OTPRateLimit.cleanup_expired()

        logger.info(
            "OTP cleanup: deleted %d OTPs, %d rate limits",
            otp_deleted,
            rate_limit_deleted,
        )

        return {
            "otps_deleted": otp_deleted,
            "rate_limits_deleted": rate_limit_deleted,
        }

    except Exception as e:
        logger.exception("OTP cleanup failed: %s", e)
        raise


@shared_task(name="core.cleanup_inactive_users")
def cleanup_inactive_users(days_inactive: int = 365):
    """Anonymize or flag users who haven't logged in for a long time.

    This task helps with GDPR compliance by identifying inactive accounts.

    Args:
        days_inactive: Number of days of inactivity

    Returns:
        dict: Statistics about flagged users
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        cutoff = timezone.now() - timezone.timedelta(days=days_inactive)

        # Find inactive users (not logged in, not staff)
        inactive_users = User.objects.filter(
            last_login__lt=cutoff,
            is_staff=False,
            is_superuser=False,
            is_active=True,
        )

        count = inactive_users.count()

        # For now, just log. In production, you might:
        # - Send re-engagement emails
        # - Flag for review
        # - Anonymize data after confirmation

        logger.info(
            "Found %d users inactive for more than %d days",
            count,
            days_inactive,
        )

        return {
            "inactive_users_count": count,
            "days_inactive": days_inactive,
        }

    except Exception as e:
        logger.exception("Inactive user cleanup failed: %s", e)
        raise


@shared_task(name="core.send_otp_email")
def send_otp_email(user_id: str, otp_id: str):
    """Send OTP via email asynchronously.

    Args:
        user_id: User UUID
        otp_id: OTP record UUID

    Returns:
        dict: Send result
    """
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail

    from core.models import OneTimePassword

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        otp = OneTimePassword.objects.get(pk=otp_id)

        if otp.is_used or otp.is_expired:
            logger.warning("OTP %s is already used or expired", otp_id)
            return {"sent": False, "reason": "OTP expired or used"}

        subject = f"Your verification code: {otp.code}"
        message = f"""
Your verification code is: {otp.code}

This code will expire in {otp.time_until_expiry.seconds // 60} minutes.

If you didn't request this code, please ignore this email.
"""

        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info("OTP email sent to %s", user.email)
        return {"sent": True, "email": user.email}

    except User.DoesNotExist:
        logger.error("User %s not found", user_id)
        return {"sent": False, "reason": "User not found"}
    except OneTimePassword.DoesNotExist:
        logger.error("OTP %s not found", otp_id)
        return {"sent": False, "reason": "OTP not found"}
    except Exception as e:
        logger.exception("Failed to send OTP email: %s", e)
        raise


@shared_task(name="core.health_check")
def periodic_health_check():
    """Periodic health check task.

    Verifies that essential services are operational.

    Returns:
        dict: Health check results
    """
    from django.core.cache import cache
    from django.db import connection

    results = {
        "timestamp": timezone.now().isoformat(),
        "database": False,
        "cache": False,
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            results["database"] = True
    except Exception as e:
        logger.error("Database health check failed: %s", e)

    # Check cache
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            results["cache"] = True
            cache.delete("health_check")
    except Exception as e:
        logger.error("Cache health check failed: %s", e)

    # Log if any service is down
    if not all([results["database"], results["cache"]]):
        logger.warning("Health check failed: %s", results)

    return results

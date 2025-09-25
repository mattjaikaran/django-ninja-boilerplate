"""Convenience functions for common email operations."""

from typing import Any

from django.conf import settings

from .service import EmailService


def send_email_template(
    template_name: str,
    context: dict[str, Any],
    recipient_email: str,
    subject: str,
    from_email: str | None = None,
) -> bool:
    """Send an email using a template - backward compatible function.

    Args:
        template_name: Path to the email template
        context: Template context variables
        recipient_email: Recipient's email address
        subject: Email subject line
        from_email: Sender's email address (uses default if None)

    Returns:
        True if email sent successfully, False otherwise
    """
    email_service = EmailService()
    template_data = {
        "html_template": template_name,
        "context": {**context, "subject": subject},
    }
    try:
        return email_service.send_templated_email(
            template_data=template_data,
            recipient_email=recipient_email,
            from_email=from_email,
        )
    except Exception:
        return False


def send_welcome_email(user_email: str, user_name: str) -> bool:
    """Send welcome email to new user.

    Args:
        user_email: User's email address
        user_name: User's display name

    Returns:
        True if email sent successfully, False otherwise
    """
    email_service = EmailService()
    context = {
        "user_name": user_name,
        "site_name": getattr(settings, "SITE_NAME", "Django Ninja Boilerplate"),
        "subject": "Welcome!",
    }

    template_data = {
        "html_template": "emails/welcome.html",
        "text_template": "emails/welcome.txt",
        "subject_template": "emails/welcome_subject.txt",
        "context": context,
    }

    try:
        return email_service.send_templated_email(
            template_data=template_data,
            recipient_email=user_email,
        )
    except Exception:
        return False

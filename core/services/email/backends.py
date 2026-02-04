"""Email backend implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Exception raised when email sending fails."""


class BaseEmailBackend(ABC):
    """Abstract base class for email backends."""

    @abstractmethod
    def send_email(
        self,
        subject: str,
        html_content: str | None,
        text_content: str | None,
        from_email: str,
        recipient_list: list[str],
        **kwargs: Any,
    ) -> bool:
        """Send email using the specific backend implementation.

        Args:
            subject: Email subject line
            html_content: HTML content of the email
            text_content: Plain text content of the email
            from_email: Sender's email address
            recipient_list: List of recipient email addresses
            **kwargs: Additional backend-specific arguments

        Returns:
            True if email was sent successfully, False otherwise

        Raises:
            EmailSendError: If email sending fails
        """


class DjangoEmailBackend(BaseEmailBackend):
    """Django's built-in email backend implementation."""

    def send_email(
        self,
        subject: str,
        html_content: str | None,
        text_content: str | None,
        from_email: str,
        recipient_list: list[str],
        **kwargs: Any,
    ) -> bool:
        """Send email using Django's EmailMultiAlternatives."""
        try:
            # Use text content as the main message
            message = text_content or strip_tags(html_content or "")

            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list,
                **kwargs,
            )

            # Add HTML alternative if provided
            if html_content:
                email.attach_alternative(html_content, "text/html")

            email.send(fail_silently=False)
            return True

        except Exception as e:
            logger.exception("Failed to send email via Django backend")
            raise EmailSendError("Failed to send email") from e


class SimpleEmailBackend(BaseEmailBackend):
    """Simple email backend using Django's send_mail function."""

    def send_email(
        self,
        subject: str,
        html_content: str | None,
        text_content: str | None,
        from_email: str,
        recipient_list: list[str],
        **kwargs: Any,
    ) -> bool:
        """Send email using Django's simple send_mail function."""
        try:
            message = text_content or strip_tags(html_content or "")

            send_mail(
                subject=subject,
                message=message,
                html_message=html_content,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            return True

        except Exception as e:
            logger.exception("Failed to send email via simple backend")
            raise EmailSendError("Failed to send email") from e

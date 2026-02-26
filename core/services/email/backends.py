"""Email backend implementations.

Backends:
- DjangoEmailBackend: Delegates to whatever EMAIL_BACKEND is configured in Django settings.
- SimpleEmailBackend: Thin wrapper around Django's send_mail helper.
- ResendEmailBackend: Django BaseEmailBackend that calls the Resend API directly.
  Docs: https://resend.com/docs/send-with-python
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.core.mail.backends.base import BaseEmailBackend as DjangoBaseEmailBackend
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


class ResendEmailBackend(DjangoBaseEmailBackend):
    """Django email backend that sends mail via the Resend API (native SDK).

    Configure by setting in Django settings:
        EMAIL_BACKEND = "core.services.email.backends.ResendEmailBackend"
        RESEND_API_KEY = "<your-resend-api-key>"

    Docs: https://resend.com/docs/send-with-python
    """

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        """Initialise the backend and configure the Resend SDK API key.

        Args:
            fail_silently: When True, swallow exceptions instead of re-raising.
            **kwargs: Forwarded to DjangoBaseEmailBackend.
        """
        super().__init__(fail_silently=fail_silently, **kwargs)
        # Import here so the package is only required when this backend is used.
        import resend
        from django.conf import settings

        api_key: str = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            logger.warning(
                "ResendEmailBackend: RESEND_API_KEY is not set. "
                "Emails will not be delivered."
            )
        resend.api_key = api_key
        self._resend = resend

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        """Send one or more EmailMessage objects via the Resend API.

        Iterates through each message and posts it to Resend's send endpoint.
        Errors are logged; when fail_silently is False the exception propagates
        after the current message, consistent with Django's SMTP backend behaviour.

        Args:
            email_messages: A list of django.core.mail.EmailMessage instances.

        Returns:
            The number of messages successfully handed off to Resend.
        """
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                # Resolve from address - prefer message's from_email, fall back to setting.
                from django.conf import settings

                from_email: str = message.from_email or getattr(
                    settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"
                )

                # Build the Resend params dict.
                params: dict[str, Any] = {
                    "from": from_email,
                    "to": list(message.to),
                    "subject": message.subject,
                    "text": message.body,
                }

                # Add CC / BCC if present.
                if message.cc:
                    params["cc"] = list(message.cc)
                if message.bcc:
                    params["bcc"] = list(message.bcc)
                if message.reply_to:
                    params["reply_to"] = list(message.reply_to)

                # Extract HTML alternative if attached.
                html_body: str | None = None
                for content, mimetype in getattr(message, "alternatives", []):
                    if mimetype == "text/html":
                        html_body = content
                        break
                if html_body:
                    params["html"] = html_body

                self._resend.Emails.send(params)
                sent_count += 1
                logger.debug(
                    "ResendEmailBackend: sent '%s' to %s",
                    message.subject,
                    message.to,
                )

            except Exception:
                logger.exception(
                    "ResendEmailBackend: failed to send '%s' to %s",
                    getattr(message, "subject", "<unknown>"),
                    getattr(message, "to", []),
                )
                if not self.fail_silently:
                    raise

        return sent_count

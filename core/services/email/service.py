"""Main email service implementation."""

import logging
from typing import Any

from django.conf import settings

from .backends import BaseEmailBackend, DjangoEmailBackend
from .templates import EmailTemplateData, EmailTemplateRenderer, dict_to_template_data

logger = logging.getLogger(__name__)


class EmailService:
    """Polymorphic email service that can handle various email scenarios."""

    def __init__(self, backend: BaseEmailBackend | None = None):
        """Initialize email service with optional backend."""
        self.backend = backend or DjangoEmailBackend()
        self.renderer = EmailTemplateRenderer()

    def send_templated_email(
        self,
        template_data: EmailTemplateData | dict[str, Any],
        recipient_email: str,
        from_email: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Send email using template data.

        Args:
            template_data: EmailTemplateData object or dict with template info
            recipient_email: Recipient's email address
            from_email: Sender's email address (uses default if None)
            **kwargs: Additional arguments passed to the backend

        Returns:
            True if email sent successfully

        Raises:
            EmailSendError: If email sending fails
        """
        if isinstance(template_data, dict):
            template_data = dict_to_template_data(template_data)

        try:
            # Render templates
            subject = self.renderer.render_subject(template_data)
            html_content = self.renderer.render_html_template(template_data)
            text_content = self.renderer.render_text_template(template_data)

            # Send email
            return self.backend.send_email(
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                **kwargs,
            )

        except Exception:
            logger.exception("Failed to send templated email")
            raise

    def send_simple_email(
        self,
        subject: str,
        message: str,
        recipient_email: str,
        html_message: str | None = None,
        from_email: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Send simple email with subject and message.

        Args:
            subject: Email subject line
            message: Plain text message
            recipient_email: Recipient's email address
            html_message: Optional HTML message
            from_email: Sender's email address (uses default if None)
            **kwargs: Additional arguments passed to the backend

        Returns:
            True if email sent successfully

        Raises:
            EmailSendError: If email sending fails
        """
        return self.backend.send_email(
            subject=subject,
            html_content=html_message,
            text_content=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            **kwargs,
        )

    def send_bulk_emails(
        self,
        email_data_list: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, int]:
        """Send bulk emails.

        Args:
            email_data_list: List of email data dictionaries
            **kwargs: Additional arguments passed to the backend

        Returns:
            Dictionary with 'sent' and 'failed' counts
        """
        sent_count = 0
        failed_count = 0

        for email_data in email_data_list:
            try:
                if "template_data" in email_data:
                    self.send_templated_email(
                        template_data=email_data["template_data"],
                        recipient_email=email_data["recipient_email"],
                        from_email=email_data.get("from_email"),
                        **kwargs,
                    )
                else:
                    self.send_simple_email(
                        subject=email_data["subject"],
                        message=email_data["message"],
                        recipient_email=email_data["recipient_email"],
                        html_message=email_data.get("html_message"),
                        from_email=email_data.get("from_email"),
                        **kwargs,
                    )
                sent_count += 1

            except Exception:
                logger.exception(
                    "Failed to send bulk email to %s",
                    email_data.get("recipient_email", "unknown"),
                )
                failed_count += 1

        return {"sent": sent_count, "failed": failed_count}

"""Email services package."""

from .backends import (
    BaseEmailBackend,
    DjangoEmailBackend,
    EmailSendError,
    ResendEmailBackend,
    SimpleEmailBackend,
)
from .service import EmailService, is_resend_backend_active
from .templates import EmailTemplateData, EmailTemplateRenderer
from .utils import (
    send_email_template,
    send_welcome_email,
)

default_email_service = EmailService()

__all__ = [
    "BaseEmailBackend",
    "DjangoEmailBackend",
    "EmailSendError",
    "EmailService",
    "EmailTemplateData",
    "EmailTemplateRenderer",
    "ResendEmailBackend",
    "SimpleEmailBackend",
    "default_email_service",
    "is_resend_backend_active",
    "send_email_template",
    "send_welcome_email",
]

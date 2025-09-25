"""Email services package."""

from .backends import BaseEmailBackend, DjangoEmailBackend, SimpleEmailBackend
from .service import EmailService
from .templates import EmailTemplateData
from .utils import (
    send_email_template,
    send_welcome_email,
)

default_email_service = EmailService()

__all__ = [
    "BaseEmailBackend",
    "DjangoEmailBackend",
    "EmailService",
    "EmailTemplateData",
    "SimpleEmailBackend",
    "default_email_service",
    "send_email_template",
    "send_welcome_email",
]

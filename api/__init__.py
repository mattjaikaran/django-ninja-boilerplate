"""Django Ninja Boilerplate API Package.

This module ensures Celery is loaded when Django starts.
"""

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from api.celery import app as celery_app

__all__ = ("celery_app",)

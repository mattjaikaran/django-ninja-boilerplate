import logging

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_notification_email(notification_id: str) -> None:
    from notifications.models import Notification

    try:
        notification = Notification.objects.select_related("user").get(
            id=notification_id
        )
    except Notification.DoesNotExist:
        logger.error("Notification %s not found", notification_id)
        return

    try:
        send_mail(
            subject=notification.title,
            message=notification.body,
            from_email=None,
            recipient_list=[notification.user.email],
            fail_silently=False,
        )
        notification.sent_at = timezone.now()
        notification.save(update_fields=["sent_at", "updated_at"])
        logger.info("Email sent for notification %s", notification_id)
    except Exception as exc:
        logger.error(
            "Failed to send email for notification %s: %s", notification_id, exc
        )
        notification.error = str(exc)
        notification.save(update_fields=["error", "updated_at"])

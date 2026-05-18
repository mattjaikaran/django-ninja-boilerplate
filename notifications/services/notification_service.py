import logging
from typing import Any

from django.core.mail import send_mail
from django.db.models import QuerySet
from django.http import Http404
from django.utils import timezone

from notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    def list_notifications(self, user: Any, unread_only: bool = False) -> QuerySet:
        qs = Notification.objects.filter(user=user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs

    def get_notification(self, notification_id: str, user: Any) -> Notification:
        try:
            return Notification.objects.get(id=notification_id, user=user)
        except Notification.DoesNotExist as err:
            raise Http404(f"Notification {notification_id} not found") from err

    def create_notification(
        self,
        user: Any,
        type: str,
        title: str,
        body: str,
        data: dict | None = None,
        action_url: str = "",
        send_email: bool = False,
    ) -> Notification:
        notification = Notification.objects.create(
            user=user,
            type=type,
            title=title,
            body=body,
            data=data or {},
            action_url=action_url,
        )
        if send_email:
            self._send_email_notification(notification)
        return notification

    def _send_email_notification(self, notification: Notification) -> None:
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
        except Exception as exc:
            logger.error(
                "Failed to send email notification %s: %s", notification.id, exc
            )
            notification.error = str(exc)
            notification.save(update_fields=["error", "updated_at"])

    def mark_read(self, notification_id: str, user: Any) -> Notification:
        notification = self.get_notification(notification_id, user)
        notification.mark_read()
        return notification

    def mark_all_read(self, user: Any) -> int:
        now = timezone.now()
        updated = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=now,
            updated_at=now,
        )
        return updated

    def delete_notification(self, notification_id: str, user: Any) -> None:
        notification = self.get_notification(notification_id, user)
        notification.delete()

    def get_unread_count(self, user: Any) -> int:
        return Notification.objects.filter(user=user, is_read=False).count()


def notify(
    user: Any,
    type: str,
    title: str,
    body: str,
    data: dict | None = None,
    action_url: str = "",
    send_email: bool = False,
) -> Notification:
    return NotificationService().create_notification(
        user, type, title, body, data or {}, action_url, send_email
    )

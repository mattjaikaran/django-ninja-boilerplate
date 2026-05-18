import logging

from ninja_extra import api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call
from notifications.schemas import NotificationListSchema, NotificationSchema
from notifications.services import NotificationService

logger = logging.getLogger(__name__)


@api_controller("/notifications", tags=["Notifications"], auth=JWTAuth())
class NotificationController:
    def __init__(self):
        self.service = NotificationService()

    @http_get("/", response={200: NotificationListSchema, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_notifications(self, request, unread_only: bool = False):
        qs = self.service.list_notifications(request.user, unread_only=unread_only)
        items = list(qs)
        unread_count = self.service.get_unread_count(request.user)
        return 200, {"unread_count": unread_count, "items": items}

    @http_get("/unread-count", response={200: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_unread_count(self, request):
        count = self.service.get_unread_count(request.user)
        return 200, {"count": count}

    # /read-all must be registered before /{notification_id} to avoid the
    # parametric route matching "read-all" as an ID
    @http_post("/read-all", response={200: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def mark_all_read(self, request):
        updated = self.service.mark_all_read(request.user)
        return 200, {"updated": updated}

    @http_get(
        "/{notification_id}", response={200: NotificationSchema, 404: dict, 500: dict}
    )
    @handle_exceptions()
    @log_api_call()
    def get_notification(self, request, notification_id: str):
        return 200, self.service.get_notification(notification_id, request.user)

    @http_post(
        "/{notification_id}/read",
        response={200: NotificationSchema, 404: dict, 500: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def mark_read(self, request, notification_id: str):
        return 200, self.service.mark_read(notification_id, request.user)

    @http_delete("/{notification_id}", response={204: None, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_notification(self, request, notification_id: str):
        self.service.delete_notification(notification_id, request.user)
        return 204, None

import logging

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call
from webhooks.schemas import (
    CreateWebhookSchema,
    UpdateWebhookSchema,
    WebhookDeliverySchema,
    WebhookSchema,
)
from webhooks.services import WebhookService

logger = logging.getLogger(__name__)


@api_controller("/webhooks", tags=["Webhooks"], auth=JWTAuth())
class WebhookController:
    def __init__(self):
        self.service = WebhookService()

    @http_get("/", response={200: list[WebhookSchema], 500: dict})
    @handle_exceptions()
    @log_api_call()
    def list_webhooks(self, request):
        return 200, self.service.list_webhooks(request.user)

    @http_post("/", response={201: WebhookSchema, 400: dict, 500: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True, include_response=False)
    def create_webhook(self, request, payload: CreateWebhookSchema):
        return 201, self.service.create_webhook(request.user, payload)

    @http_get("/{webhook_id}", response={200: WebhookSchema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def get_webhook(self, request, webhook_id: str):
        return 200, self.service.get_webhook(webhook_id, request.user)

    @http_put("/{webhook_id}", response={200: WebhookSchema, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_webhook(self, request, webhook_id: str, payload: UpdateWebhookSchema):
        return 200, self.service.update_webhook(webhook_id, request.user, payload)

    @http_delete("/{webhook_id}", response={204: None, 404: dict, 500: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_webhook(self, request, webhook_id: str):
        self.service.delete_webhook(webhook_id, request.user)
        return 204, None

    @http_get(
        "/{webhook_id}/deliveries",
        response={200: list[WebhookDeliverySchema], 404: dict, 500: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def list_deliveries(self, request, webhook_id: str):
        return 200, self.service.list_deliveries(webhook_id, request.user)

    @http_post(
        "/deliveries/{delivery_id}/retry",
        response={200: WebhookDeliverySchema, 404: dict, 500: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def retry_delivery(self, request, delivery_id: str):
        return 200, self.service.retry_delivery(delivery_id, request.user)

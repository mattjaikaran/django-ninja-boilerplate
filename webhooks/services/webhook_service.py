import logging
from typing import Any

from django.db.models import QuerySet
from django.http import Http404

from webhooks.models import Webhook, WebhookDelivery
from webhooks.schemas import CreateWebhookSchema, UpdateWebhookSchema

logger = logging.getLogger(__name__)


class WebhookService:
    def list_webhooks(self, user: Any) -> QuerySet:
        return Webhook.objects.filter(created_by=user, is_active=True)

    def get_webhook(self, webhook_id: str, user: Any) -> Webhook:
        try:
            return Webhook.objects.get(id=webhook_id, created_by=user)
        except Webhook.DoesNotExist as err:
            raise Http404(f"Webhook {webhook_id} not found") from err

    def create_webhook(self, user: Any, data: CreateWebhookSchema) -> Webhook:
        webhook = Webhook.objects.create(
            created_by=user,
            **data.model_dump(),
        )
        logger.info("Created webhook: %s (id=%s)", webhook.name, webhook.id)
        return webhook

    def update_webhook(
        self, webhook_id: str, user: Any, data: UpdateWebhookSchema
    ) -> Webhook:
        webhook = self.get_webhook(webhook_id, user)
        for attr, value in data.model_dump(exclude_unset=True).items():
            setattr(webhook, attr, value)
        webhook.save()
        logger.info("Updated webhook: %s (id=%s)", webhook.name, webhook.id)
        return webhook

    def delete_webhook(self, webhook_id: str, user: Any) -> None:
        webhook = self.get_webhook(webhook_id, user)
        logger.info("Deleting webhook: %s (id=%s)", webhook.name, webhook.id)
        webhook.delete()

    def list_deliveries(self, webhook_id: str, user: Any) -> QuerySet:
        webhook = self.get_webhook(webhook_id, user)
        return webhook.deliveries.all()

    def retry_delivery(self, delivery_id: str, user: Any) -> WebhookDelivery:
        try:
            delivery = WebhookDelivery.objects.select_related("webhook").get(
                id=delivery_id,
                webhook__created_by=user,
            )
        except WebhookDelivery.DoesNotExist as err:
            raise Http404(f"Delivery {delivery_id} not found") from err

        from webhooks.tasks import deliver_webhook

        deliver_webhook.delay(str(delivery.id))
        logger.info("Queued retry for delivery %s", delivery.id)
        return delivery

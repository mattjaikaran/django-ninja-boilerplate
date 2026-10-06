import logging
from typing import Any

from django.db.models import QuerySet
from django.http import Http404

from api.exceptions import ValidationError
from webhooks.models import Webhook, WebhookDelivery
from webhooks.schemas import CreateWebhookSchema, UpdateWebhookSchema
from webhooks.ssrf import UnsafeWebhookURLError, validate_webhook_url

logger = logging.getLogger(__name__)


def _check_url(url: str) -> None:
    """Reject URLs that delivery would block (scheme, non-public address)."""
    try:
        validate_webhook_url(url)
    except UnsafeWebhookURLError as exc:
        raise ValidationError(str(exc), details={"field": "url"}) from exc


class WebhookService:
    def list_webhooks(self, user: Any) -> QuerySet:
        return Webhook.objects.filter(created_by=user, is_active=True)

    def get_webhook(self, webhook_id: str, user: Any) -> Webhook:
        try:
            return Webhook.objects.get(id=webhook_id, created_by=user)
        except Webhook.DoesNotExist as err:
            raise Http404(f"Webhook {webhook_id} not found") from err

    def create_webhook(self, user: Any, data: CreateWebhookSchema) -> Webhook:
        _check_url(data.url)
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
        changes = data.model_dump(exclude_unset=True)
        if changes.get("url") is not None:
            _check_url(changes["url"])
        for attr, value in changes.items():
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

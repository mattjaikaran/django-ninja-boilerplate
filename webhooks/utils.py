import logging

from webhooks.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


def dispatch_webhook(event: str, payload: dict) -> None:
    active_webhooks = Webhook.objects.filter(is_active=True)
    webhooks = [w for w in active_webhooks if event in (w.events or [])]

    for webhook in webhooks:
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event=event,
            payload=payload,
        )
        from webhooks.tasks import deliver_webhook

        deliver_webhook.delay(str(delivery.id))
        logger.info(
            "Dispatched webhook %s for event %s (delivery=%s)",
            webhook.id,
            event,
            delivery.id,
        )

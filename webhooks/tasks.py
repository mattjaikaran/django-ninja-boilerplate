import hashlib
import hmac
import json
import logging
from datetime import timedelta

from django.utils import timezone

from api.tasks import shared_task
from webhooks.ssrf import UnsafeWebhookURLError, post_webhook

logger = logging.getLogger(__name__)


@shared_task(max_retries=5)
def deliver_webhook(delivery_id: str) -> None:
    from webhooks.models import WebhookDelivery

    try:
        delivery = WebhookDelivery.objects.select_related("webhook").get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.error("WebhookDelivery %s not found", delivery_id)
        return

    webhook = delivery.webhook
    payload_bytes = json.dumps(delivery.payload).encode()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": delivery.event,
        **webhook.headers,
    }

    if webhook.secret:
        signature = hmac.new(
            webhook.secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    try:
        response = post_webhook(webhook.url, payload_bytes, headers)
        delivery.response_status = response.status_code
        delivery.response_body = response.body
        delivery.delivered_at = timezone.now()
        delivery.error = ""
        delivery.save(
            update_fields=[
                "response_status",
                "response_body",
                "delivered_at",
                "error",
                "updated_at",
            ]
        )
    except Exception as exc:
        delivery.attempt_count += 1
        delivery.error = str(exc)
        if isinstance(exc, UnsafeWebhookURLError) and not exc.retryable:
            # A blocked target stays blocked; retrying only repeats the request.
            delivery.save(update_fields=["attempt_count", "error", "updated_at"])
            logger.warning("Webhook delivery %s blocked: %s", delivery_id, exc)
            return
        countdown = (2**delivery.attempt_count) * 60
        delivery.next_retry_at = timezone.now() + timedelta(seconds=countdown)
        delivery.save(
            update_fields=["attempt_count", "error", "next_retry_at", "updated_at"]
        )
        logger.warning(
            "Webhook delivery %s failed (attempt %d): %s",
            delivery_id,
            delivery.attempt_count,
            exc,
        )
        raise deliver_webhook.retry(
            delivery_id,
            exc=exc,
            countdown=countdown,
        )

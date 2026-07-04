"""API Key authentication for Django Ninja."""

import logging

from django.utils import timezone
from ninja.security import APIKeyHeader

logger = logging.getLogger(__name__)


class APIKeyAuth(APIKeyHeader):
    """Authenticate requests via X-API-Key header.

    Key format: {prefix}.{secret}
    Lookup by prefix, verify by SHA-256 hash comparison.
    Sets request.user to key owner and request.auth to the APIKey instance.
    """

    param_name = "X-API-Key"

    def authenticate(self, request, key: str | None) -> object | None:
        if not key or "." not in key:
            return None

        from core.models.api_key import APIKey

        prefix = key.split(".", 1)[0]

        try:
            api_key = APIKey.objects.select_related("user").get(
                prefix=prefix,
                revoked=False,
            )
        except APIKey.DoesNotExist:
            return None

        if not api_key.verify(key):
            return None

        if not api_key.is_valid:
            return None

        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        request.auth = api_key
        return api_key.user

"""Business logic for API key management."""

from datetime import timedelta

from django.utils import timezone

from core.models.api_key import APIKey


class APIKeyService:
    """Service for creating, revoking, and rotating API keys."""

    @staticmethod
    def create_key(
        user,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> tuple[APIKey, str]:
        """Create a new API key.

        Returns:
            Tuple of (APIKey instance, raw_key string).
            The raw_key is only available at creation time.
        """
        prefix, raw_key, hashed = APIKey.generate_key()

        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        api_key = APIKey.objects.create(
            prefix=prefix,
            hashed_key=hashed,
            name=name,
            user=user,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        return api_key, raw_key

    @staticmethod
    def revoke_key(user, key_id: str) -> APIKey:
        """Revoke an API key."""
        api_key = APIKey.objects.get(id=key_id, user=user, revoked=False)
        api_key.revoked = True
        api_key.save(update_fields=["revoked", "updated_at"])
        return api_key

    @staticmethod
    def rotate_key(user, key_id: str) -> tuple[APIKey, str, APIKey]:
        """Rotate an API key: revoke old, create new with same config.

        Returns:
            Tuple of (new_api_key, new_raw_key, old_api_key).
        """
        old_key = APIKey.objects.get(id=key_id, user=user, revoked=False)

        old_key.revoked = True
        old_key.save(update_fields=["revoked", "updated_at"])

        new_key, raw_key = APIKeyService.create_key(
            user=user,
            name=old_key.name,
            scopes=old_key.scopes,
            expires_in_days=None,
        )
        if old_key.expires_at:
            new_key.expires_at = old_key.expires_at
            new_key.save(update_fields=["expires_at"])

        return new_key, raw_key, old_key

    @staticmethod
    def list_keys(user, include_revoked: bool = False):
        """List API keys for a user."""
        qs = APIKey.objects.filter(user=user)
        if not include_revoked:
            qs = qs.filter(revoked=False)
        return qs

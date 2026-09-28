"""Management command to flush expired JWT tokens from the blacklist.

This command is the portable, backend-neutral entry point for pruning the
``ninja_jwt.token_blacklist`` outstanding-token table. It can be invoked
directly by a platform scheduler (cron, systemd timer, Kubernetes CronJob)
independently of the configured task backend; the Celery beat schedule in
``api/celery.py`` runs the same flush via ``core.flush_expired_tokens``.

    python manage.py flush_expired_tokens
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete expired JWT tokens from the token blacklist outstanding-token list"

    def handle(self, *args, **options):
        from core.tasks import flush_expired_tokens

        result = flush_expired_tokens()
        self.stdout.write(
            self.style.SUCCESS(f"Flushed {result['deleted']} expired JWT token(s)")
        )

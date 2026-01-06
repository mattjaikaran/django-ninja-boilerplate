"""Management command to clean up expired OTP codes.

This command can be run manually or via cron/Celery beat to remove
old OTP records and rate limit entries.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Clean up expired OTP codes and rate limit entries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Delete OTPs older than this many days (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        from core.models import OneTimePassword
        from core.models.otp import OTPRateLimit

        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timezone.timedelta(days=days)

        self.stdout.write(f"\n🧹 OTP Cleanup (older than {days} days)")
        self.stdout.write("-" * 40)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        # Count OTPs to delete
        old_otps = OneTimePassword.objects.filter(created_at__lt=cutoff)
        otp_count = old_otps.count()

        # Count used OTPs
        used_otps = OneTimePassword.objects.filter(is_used=True)
        used_count = used_otps.count()

        # Count expired rate limits
        rate_limit_cutoff = timezone.now() - timezone.timedelta(hours=24)
        old_rate_limits = OTPRateLimit.objects.filter(
            window_start__lt=rate_limit_cutoff
        )
        rate_limit_count = old_rate_limits.count()

        self.stdout.write(f"OTPs older than {days} days: {otp_count}")
        self.stdout.write(f"Used OTPs: {used_count}")
        self.stdout.write(f"Expired rate limits: {rate_limit_count}")

        if not dry_run:
            # Delete old OTPs
            otp_deleted, _ = old_otps.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ Deleted {otp_deleted} old OTPs"))

            # Delete rate limits
            rate_limit_deleted = OTPRateLimit.cleanup_expired()
            self.stdout.write(
                self.style.SUCCESS(f"✅ Deleted {rate_limit_deleted} rate limits")
            )

            # Summary
            total = otp_deleted + rate_limit_deleted
            self.stdout.write(
                self.style.SUCCESS(f"\n🎉 Total cleaned: {total} records")
            )
        else:
            total = otp_count + rate_limit_count
            self.stdout.write(self.style.WARNING(f"\n📊 Would delete: {total} records"))

        # Show current stats
        self.stdout.write("\n📈 Current Statistics:")
        self.stdout.write(f"   Total OTPs: {OneTimePassword.objects.count()}")
        self.stdout.write(
            f"   Active OTPs: {OneTimePassword.objects.filter(is_used=False, expires_at__gte=timezone.now()).count()}"
        )
        self.stdout.write(f"   Rate limits: {OTPRateLimit.objects.count()}")

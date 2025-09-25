"""Management command to generate feature modules with optional integrations."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Generate feature modules with optional integrations like payments, Redis, etc."""

    help = "Generate feature modules with optional integrations"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "feature_type",
            choices=[
                "payments",
                "redis",
                "rbac",
                "organization",
                "team",
                "subscription",
                "notification",
                "chat",
                "file_storage",
                "analytics",
                "api_endpoint",
                "monitoring",
                "cache",
            ],
            help="Type of feature to generate",
        )
        parser.add_argument(
            "--app-name",
            type=str,
            help="Name of the Django app to create (defaults to feature type)",
        )
        parser.add_argument(
            "--provider",
            type=str,
            choices=["stripe", "paypal", "aws", "gcp", "local"],
            help="Provider for the feature (e.g., stripe for payments)",
        )
        parser.add_argument(
            "--platform-type",
            type=str,
            choices=["b2c", "b2b", "marketplace", "saas"],
            default="b2c",
            help="Platform type to optimize for",
        )
        parser.add_argument(
            "--no-subscriptions",
            action="store_true",
            help="Skip subscription functionality for payments",
        )
        parser.add_argument(
            "--no-webhooks",
            action="store_true",
            help="Skip webhook functionality",
        )
        parser.add_argument(
            "--minimal",
            action="store_true",
            help="Generate minimal version without advanced features",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command execution."""
        feature_type = options["feature_type"]
        app_name = options.get("app_name") or feature_type
        provider = options.get("provider")
        platform_type = options["platform_type"]

        self.stdout.write(self.style.SUCCESS(f"Generating {feature_type} feature..."))

        try:
            if feature_type == "payments":
                self._generate_payments_feature(
                    app_name, provider, platform_type, options
                )
            elif feature_type == "redis":
                self._generate_redis_feature(app_name, options)
            elif feature_type == "rbac":
                self._generate_rbac_feature(app_name, platform_type, options)
            elif feature_type == "organization":
                self._generate_organization_feature(app_name, platform_type, options)
            elif feature_type == "team":
                self._generate_team_feature(app_name, platform_type, options)
            elif feature_type == "subscription":
                self._generate_subscription_feature(app_name, provider, options)
            elif feature_type == "notification":
                self._generate_notification_feature(app_name, options)
            elif feature_type == "chat":
                self._generate_chat_feature(app_name, options)
            elif feature_type == "file_storage":
                self._generate_file_storage_feature(app_name, provider, options)
            elif feature_type == "analytics":
                self._generate_analytics_feature(app_name, options)
            elif feature_type == "api_endpoint":
                self._generate_api_endpoint_feature(app_name, options)
            elif feature_type == "monitoring":
                self._generate_monitoring_feature(app_name, options)
            elif feature_type == "cache":
                self._generate_cache_feature(app_name, options)
            else:
                raise CommandError(f"Unsupported feature type: {feature_type}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully generated {feature_type} feature in '{app_name}' app"
                )
            )

        except Exception as e:
            raise CommandError(f"Failed to generate {feature_type} feature: {e}")

    def _generate_payments_feature(
        self, app_name: str, provider: str | None, platform_type: str, options: dict
    ) -> None:
        """Generate payments feature with Stripe integration."""
        from .generators.payments_generator import PaymentsGenerator

        generator = PaymentsGenerator(
            app_name=app_name,
            provider=provider or "stripe",
            platform_type=platform_type,
            include_subscriptions=not options.get("no_subscriptions", False),
            include_webhooks=not options.get("no_webhooks", False),
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_redis_feature(self, app_name: str, options: dict) -> None:
        """Generate Redis integration feature."""
        from .generators.redis_generator import RedisGenerator

        generator = RedisGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_rbac_feature(
        self, app_name: str, platform_type: str, options: dict
    ) -> None:
        """Generate RBAC (Role-Based Access Control) feature."""
        from .generators.rbac_generator import RBACGenerator

        generator = RBACGenerator(
            app_name=app_name,
            platform_type=platform_type,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_organization_feature(
        self, app_name: str, platform_type: str, options: dict
    ) -> None:
        """Generate organization/company management feature."""
        from .generators.organization_generator import OrganizationGenerator

        generator = OrganizationGenerator(
            app_name=app_name,
            platform_type=platform_type,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_team_feature(
        self, app_name: str, platform_type: str, options: dict
    ) -> None:
        """Generate team management feature."""
        from .generators.team_generator import TeamGenerator

        generator = TeamGenerator(
            app_name=app_name,
            platform_type=platform_type,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_subscription_feature(
        self, app_name: str, provider: str | None, options: dict
    ) -> None:
        """Generate subscription management feature."""
        from .generators.subscription_generator import SubscriptionGenerator

        generator = SubscriptionGenerator(
            app_name=app_name,
            provider=provider or "stripe",
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_notification_feature(self, app_name: str, options: dict) -> None:
        """Generate notification system feature."""
        from .generators.notification_generator import NotificationGenerator

        generator = NotificationGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_chat_feature(self, app_name: str, options: dict) -> None:
        """Generate chat/messaging feature."""
        from .generators.chat_generator import ChatGenerator

        generator = ChatGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_file_storage_feature(
        self, app_name: str, provider: str | None, options: dict
    ) -> None:
        """Generate file storage feature."""
        from .generators.file_storage_generator import FileStorageGenerator

        generator = FileStorageGenerator(
            app_name=app_name,
            provider=provider or "local",
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_analytics_feature(self, app_name: str, options: dict) -> None:
        """Generate analytics tracking feature."""
        from .generators.analytics_generator import AnalyticsGenerator

        generator = AnalyticsGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_api_endpoint_feature(self, app_name: str, options: dict) -> None:
        """Generate API endpoint feature with full CRUD operations."""
        from .generators.api_endpoint_generator import ApiEndpointGenerator

        generator = ApiEndpointGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_monitoring_feature(self, app_name: str, options: dict) -> None:
        """Generate monitoring and metrics feature."""
        from .generators.monitoring_generator import MonitoringGenerator

        generator = MonitoringGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

    def _generate_cache_feature(self, app_name: str, options: dict) -> None:
        """Generate advanced caching feature."""
        from .generators.cache_generator import CacheGenerator

        generator = CacheGenerator(
            app_name=app_name,
            minimal=options.get("minimal", False),
        )
        generator.generate()

"""Management command to generate feature modules."""

import importlib
import importlib.util
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .generators.base_generator import BaseGenerator

# Feature type -> (module in .generators, generator class).
GENERATORS = {
    "payments": ("payments_generator", "PaymentsGenerator"),
    "redis": ("redis_generator", "RedisGenerator"),
    "rbac": ("rbac_generator", "RBACGenerator"),
    "organization": ("organization_generator", "OrganizationGenerator"),
    "team": ("team_generator", "TeamGenerator"),
    "notification": ("notification_generator", "NotificationGenerator"),
    "chat": ("chat_generator", "ChatGenerator"),
    "analytics": ("analytics_generator", "AnalyticsGenerator"),
    "api_endpoint": ("api_endpoint_generator", "ApiEndpointGenerator"),
    "graphql": ("graphql_generator", "GraphQLGenerator"),
}
# Features whose generator takes a platform type.
PLATFORM_FEATURES = {"payments", "rbac", "organization", "team"}

# Default app names for features whose own name is an installed module.
# Without --app-name the app name is the feature type.
DEFAULT_APP_NAMES = {"redis": "cache_api"}


def shadowed_module(app_name: str, project_root: Path) -> str | None:
    """Return where ``app_name`` imports from when it is not the project's app.

    An app named after an importable module, such as ``redis`` or
    ``graphql``, would shadow that module. Return None when nothing is
    importable under the name or when the name resolves to
    ``project_root/app_name``, an app that already exists in the project.
    """
    if not app_name.isidentifier():
        return None
    spec = importlib.util.find_spec(app_name)
    if spec is None:
        return None
    app_dir = (project_root / app_name).resolve()
    locations = list(spec.submodule_search_locations or [])
    if any(Path(location).resolve() == app_dir for location in locations):
        return None
    return spec.origin or ", ".join(locations)


class Command(BaseCommand):
    """Generate a feature app, such as payments, RBAC or a cache API."""

    help = "Generate a feature app and register it in the project"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "feature_type",
            choices=list(GENERATORS),
            help="Type of feature to generate",
        )
        parser.add_argument(
            "--app-name",
            type=str,
            help=(
                "Name of the Django app to create. Defaults to the feature "
                "type; redis defaults to cache_api"
            ),
        )
        parser.add_argument(
            "--provider",
            type=str,
            choices=["stripe"],
            help="Payments provider. Only stripe is supported",
        )
        parser.add_argument(
            "--platform-type",
            type=str,
            choices=["b2c", "b2b", "marketplace", "saas"],
            default="b2c",
            help="Platform type, shown in the generator log",
        )
        parser.add_argument(
            "--no-subscriptions",
            action="store_true",
            help="Payments: skip the subscription models",
        )
        parser.add_argument(
            "--minimal",
            action="store_true",
            help="Organization: set ORGANIZATION_MAX_MEMBERS to 100, not 1000",
        )
        parser.add_argument(
            "--realtime",
            action="store_true",
            help="Chat: add a Centrifugo ChatRealtimeService",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command execution."""
        feature_type = options["feature_type"]
        app_name = options.get("app_name") or DEFAULT_APP_NAMES.get(
            feature_type, feature_type
        )
        origin = shadowed_module(app_name, Path.cwd())
        if origin:
            msg = (
                f"App name '{app_name}' shadows the installed module "
                f"'{app_name}' ({origin}). Pass another name with --app-name."
            )
            raise CommandError(msg)
        # The generators format their output with ruff. Check before writing
        # anything, so a venv without the dev extra never leaves a half-wired app.
        if importlib.util.find_spec("ruff") is None:
            msg = "generate_feature needs ruff from the dev extra: run `uv sync --extra dev`."
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS(f"Generating {feature_type} feature..."))
        try:
            self._generator(feature_type, app_name, options).generate()
        except Exception as e:
            msg = f"Failed to generate {feature_type} feature: {e}"
            raise CommandError(msg) from e
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated {feature_type} feature in '{app_name}' app"
            )
        )

    def _generator(
        self, feature_type: str, app_name: str, options: dict[str, Any]
    ) -> BaseGenerator:
        """Return the generator for ``feature_type`` with its options."""
        module_name, class_name = GENERATORS[feature_type]
        module = importlib.import_module(f".generators.{module_name}", __package__)
        kwargs: dict[str, Any] = {"app_name": app_name}
        if feature_type != "analytics":
            kwargs["minimal"] = options["minimal"]
        if feature_type in PLATFORM_FEATURES:
            kwargs["platform_type"] = options["platform_type"]
        if feature_type == "payments":
            kwargs["provider"] = options["provider"] or "stripe"
            kwargs["include_subscriptions"] = not options["no_subscriptions"]
        if feature_type == "chat":
            kwargs["realtime"] = options["realtime"]
        generator: BaseGenerator = getattr(module, class_name)(**kwargs)
        return generator

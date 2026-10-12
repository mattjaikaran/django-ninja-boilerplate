"""Organization feature generator."""

from .base_generator import BaseGenerator, GeneratorError
from .templates.organization_templates import render_organization_files


class OrganizationGenerator(BaseGenerator):
    """Generator for the organization management feature.

    The app gets organization and invitation controllers behind ``JWTAuth``,
    a service that scopes every query to the user's memberships, and one
    smoke and permission test file.
    """

    def __init__(
        self,
        app_name: str = "organizations",
        platform_type: str = "b2b",
        minimal: bool = False,
    ):
        """Initialize the organization generator."""
        super().__init__(app_name, minimal)
        self.platform_type = platform_type

    def generate(self) -> None:
        """Generate the organization feature."""
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        self.logger.info(
            "Generating organization feature for a %s platform in %s...",
            self.platform_type,
            self.app_name,
        )
        self.create_django_app()
        self.remove_scaffold()
        for relative_path, content in render_organization_files(self.app_name).items():
            self.create_file(self.app_path / relative_path, content)

        # OrganizationService reads these settings when it invites members.
        self.update_settings(
            self.app_name,
            {
                "ORGANIZATION_INVITATION_EXPIRY_DAYS": 7,
                "ORGANIZATION_MAX_MEMBERS": 100 if self.minimal else 1000,
            },
        )
        self.update_urls(
            self.app_name, "OrganizationController", "OrganizationInvitationController"
        )
        self.create_migration()
        self.logger.info(
            "Organization feature generated at /api/organizations/ and "
            "/api/invitations/"
        )

"""Team feature generator."""

from .base_generator import BaseGenerator
from .templates.controller_templates import MODERN_CONTROLLER_TEMPLATE


class TeamGenerator(BaseGenerator):
    """Generator for team management feature."""

    def __init__(
        self,
        app_name: str = "teams",
        platform_type: str = "saas",
        minimal: bool = False,
    ):
        """Initialize the team generator."""
        super().__init__(app_name, minimal)
        self.platform_type = platform_type

    def generate(self) -> None:
        """Generate the team feature."""
        print(f"Generating team feature for {self.platform_type} platform...")

        # Create Django app
        self.create_django_app()

        # Generate models
        self._generate_models()

        # Generate schemas
        self._generate_schemas()

        # Generate controllers
        self._generate_controllers()

        # Generate admin
        self._generate_admin()

        # Update settings
        self._update_settings()

        # Update URLs
        self.update_urls(self.app_name)

        # Create migrations
        self.create_migration()

        print("Team feature generated successfully!")

    def _generate_models(self) -> None:
        """Generate team models."""
        models_content = '''"""Team models."""

from django.db import models
from django.conf import settings
from core.models import AbstractBaseModel


class Team(AbstractBaseModel):
    """Team model for organizing users."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Optional organization relationship
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="teams",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamMember(AbstractBaseModel):
    """Team membership model."""

    ROLE_CHOICES = [
        ("lead", "Team Lead"),
        ("senior", "Senior Member"),
        ("member", "Member"),
        ("junior", "Junior Member"),
    ]

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["team", "user"]
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"

    def __str__(self):
        return f"{self.user.username} - {self.team.name} ({self.role})"

    @property
    def is_lead(self):
        return self.role == "lead"
'''

        self.create_file(self.app_path / "models" / "team.py", models_content)

        # Update models __init__.py
        init_content = """from .team import Team, TeamMember

__all__ = ["Team", "TeamMember"]
"""
        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _generate_schemas(self) -> None:
        """Generate team schemas."""
        schemas_content = '''"""Team schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import Optional, List


class TeamSchema(CamelCaseSchema):
    id: str
    name: str
    description: str
    is_active: bool
    organization_id: Optional[str] = None
    created_at: str
    updated_at: str


class CreateTeamSchema(CamelCaseSchema):
    name: str
    description: str = ""
    organization_id: Optional[str] = None


class UpdateTeamSchema(CamelCaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberSchema(CamelCaseSchema):
    id: str
    team: TeamSchema
    user_id: str
    username: str
    role: str
    is_active: bool
    created_at: str


class AddMemberSchema(CamelCaseSchema):
    user_id: str
    role: str = "member"


class UpdateMemberRoleSchema(CamelCaseSchema):
    role: str
'''

        self.create_file(self.app_path / "schemas" / "team_schema.py", schemas_content)

    def _generate_controllers(self) -> None:
        """Generate team controllers."""
        # Use modern controller template with team-specific context
        controller_content = MODERN_CONTROLLER_TEMPLATE.format(
            app_name=self.app_name,
            model_name="Team",
            model_name_lower="team",
            model_name_plural="Teams",
            url_prefix="teams",
            search_filter_class="TeamSearchFilter",
            select_related='["organization", "members"]',
            search_fields='["name", "description"]',
            filter_fields="""{"is_active": "boolean", "organization": "exact"}""",
            ordering_fields='["name", "created_at", "updated_at"]',
        )

        self.create_file(
            self.app_path / "controllers" / "team_controller.py", controller_content
        )

    def _generate_admin(self) -> None:
        """Generate team admin."""
        admin_content = f'''"""Team admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {self.app_name}.models import Team, TeamMember


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ["name", "organization", "is_active", "member_count", "created_at"]
    list_filter = ["is_active", "organization", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Members"


@admin.register(TeamMember)
class TeamMemberAdmin(ModelAdmin):
    list_display = ["user", "team", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active", "team", "created_at"]
    search_fields = ["user__username", "user__email", "team__name"]
    readonly_fields = ["created_at", "updated_at"]
'''

        self.create_file(self.app_path / "admin" / "team_admin.py", admin_content)

    def _update_settings(self) -> None:
        """Update Django settings for teams."""
        settings_updates = {
            "TEAM_MAX_MEMBERS": 20 if self.minimal else 100,
            "TEAM_AUTO_JOIN": False,
        }
        self.update_settings(self.app_name, settings_updates)

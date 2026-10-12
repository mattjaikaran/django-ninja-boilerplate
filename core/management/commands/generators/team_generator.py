"""Team feature generator.

Members see their teams; only a team lead changes a team or its members.
Every query is scoped to the requesting user's memberships (AGENTS.md
section 08).
"""

from .base_generator import BaseGenerator
from .codegen import from_import, import_block, package_init

TEAM_MODELS_TEMPLATE = '''"""Team models."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class TeamRole(models.TextChoices):
    """Roles a member can hold in a team. A lead manages the team."""

    LEAD = "lead", "Team Lead"
    SENIOR = "senior", "Senior Member"
    MEMBER = "member", "Member"
    JUNIOR = "junior", "Junior Member"


class Team(AbstractBaseModel):
    """A group of users. Members see the team; leads manage it."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamMember(AbstractBaseModel):
    """Membership of one user in one team."""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=20, choices=TeamRole.choices, default=TeamRole.MEMBER
    )

    class Meta:
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"], name="%(app_label)s_unique_team_member"
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.team} ({self.role})"
'''

TEAM_SCHEMAS_TEMPLATE = '''"""Team schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, Field

{first_party_imports}

# Serialize UUID primary and foreign keys as strings.
IdStr = Annotated[str, BeforeValidator(str)]


class TeamSchema(CamelCaseSchema):
    id: IdStr
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class CreateTeamSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class UpdateTeamSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class TeamMemberSchema(CamelCaseSchema):
    id: IdStr
    team_id: IdStr
    user_id: IdStr
    role: TeamRole
    created_at: datetime


class AddTeamMemberSchema(CamelCaseSchema):
    user_id: UUID
    role: TeamRole = TeamRole.MEMBER


class UpdateTeamMemberSchema(CamelCaseSchema):
    role: TeamRole
'''

TEAM_SERVICE_TEMPLATE = '''"""Business logic for teams. Every query is scoped to the user's memberships."""

from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

{first_party_imports}


class TeamService:
    """Membership-scoped teams. Only a team lead changes a team or its members."""

    def list_for_user(self, user: Any) -> QuerySet[Team]:
        """Return the teams the user belongs to."""
        return Team.objects.filter(members__user=user).order_by("name")

    def get_for_user(self, team_id: UUID, user: Any) -> Team:
        """Return a team the user belongs to. Raise Http404 for any other team."""
        return get_object_or_404(Team, id=team_id, members__user=user)

    def create(self, user: Any, payload: CreateTeamSchema) -> Team:
        """Create a team with the user as its lead."""
        with transaction.atomic():
            team = Team.objects.create(
                name=payload.name, description=payload.description
            )
            TeamMember.objects.create(team=team, user=user, role=TeamRole.LEAD)
        return team

    def update(self, team_id: UUID, user: Any, payload: UpdateTeamSchema) -> Team:
        """Apply the set fields of the payload to a team the user leads."""
        team = self.get_led_team(team_id, user)
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(team, field, value)
        team.save()
        return team

    def delete(self, team_id: UUID, user: Any) -> None:
        """Delete a team the user leads."""
        self.get_led_team(team_id, user).delete()

    def list_members(self, team_id: UUID, user: Any) -> QuerySet[TeamMember]:
        """Return the members of a team the user belongs to."""
        return self.get_for_user(team_id, user).members.order_by("created_at")

    def add_member(
        self, team_id: UUID, user: Any, payload: AddTeamMemberSchema
    ) -> TeamMember:
        """Add a user to a team the requesting user leads."""
        team = self.get_led_team(team_id, user)
        new_member = get_object_or_404(get_user_model(), id=payload.user_id)
        if team.members.filter(user=new_member).exists():
            raise ConflictError("The user is already a member of this team")
        return TeamMember.objects.create(team=team, user=new_member, role=payload.role)

    def update_member_role(
        self,
        team_id: UUID,
        member_id: UUID,
        user: Any,
        payload: UpdateTeamMemberSchema,
    ) -> TeamMember:
        """Change the role of a member in a team the user leads."""
        team = self.get_led_team(team_id, user)
        member = get_object_or_404(TeamMember, id=member_id, team=team)
        member.role = payload.role
        member.save(update_fields=["role", "updated_at"])
        return member

    def remove_member(self, team_id: UUID, member_id: UUID, user: Any) -> None:
        """Remove a member from a team the user leads."""
        team = self.get_led_team(team_id, user)
        get_object_or_404(TeamMember, id=member_id, team=team).delete()

    def get_led_team(self, team_id: UUID, user: Any) -> Team:
        """Return a team the user leads. Non-members get 404, other members 403."""
        team = self.get_for_user(team_id, user)
        if not team.members.filter(user=user, role=TeamRole.LEAD).exists():
            raise APIPermissionError("Only a team lead can change this team")
        return team
'''

TEAM_CONTROLLER_TEMPLATE = '''"""Team controller. The service scopes every route to the user's teams."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/teams", tags=["Teams"], auth=JWTAuth())
class TeamController:
    """Teams of the authenticated user. Team leads manage them.

    Put static paths before the first /{{team_id}} handler.
    """

    def __init__(self):
        self.service = TeamService()

    @http_get("/", response={{200: list[TeamSchema]}})
    @log_api_call()
    def list_teams(self, request):
        """List the user's teams."""
        return 200, self.service.list_for_user(request.user)

    @http_post("/", response={{201: TeamSchema}})
    @log_api_call(include_payload=True)
    def create_team(self, request, payload: CreateTeamSchema):
        """Create a team with the user as its lead."""
        return 201, self.service.create(request.user, payload)

    @http_get("/{{team_id}}", response={{200: TeamSchema, 404: dict}})
    @log_api_call()
    def get_team(self, request, team_id: UUID):
        """Get one of the user's teams."""
        return 200, self.service.get_for_user(team_id, request.user)

    @http_put("/{{team_id}}", response={{200: TeamSchema, 403: dict, 404: dict}})
    @log_api_call(include_payload=True)
    def update_team(self, request, team_id: UUID, payload: UpdateTeamSchema):
        """Update a team the user leads."""
        return 200, self.service.update(team_id, request.user, payload)

    @http_delete("/{{team_id}}", response={{204: None, 403: dict, 404: dict}})
    @log_api_call()
    def delete_team(self, request, team_id: UUID):
        """Delete a team the user leads."""
        self.service.delete(team_id, request.user)
        return 204, None

    @http_get("/{{team_id}}/members", response={{200: list[TeamMemberSchema], 404: dict}})
    @log_api_call()
    def list_members(self, request, team_id: UUID):
        """List the members of one of the user's teams."""
        return 200, self.service.list_members(team_id, request.user)

    @http_post(
        "/{{team_id}}/members",
        response={{201: TeamMemberSchema, 403: dict, 404: dict, 409: dict}},
    )
    @log_api_call(include_payload=True)
    def add_member(self, request, team_id: UUID, payload: AddTeamMemberSchema):
        """Add a member to a team the user leads."""
        return 201, self.service.add_member(team_id, request.user, payload)

    @http_put(
        "/{{team_id}}/members/{{member_id}}",
        response={{200: TeamMemberSchema, 403: dict, 404: dict}},
    )
    @log_api_call(include_payload=True)
    def update_member_role(
        self,
        request,
        team_id: UUID,
        member_id: UUID,
        payload: UpdateTeamMemberSchema,
    ):
        """Change a member's role in a team the user leads."""
        member = self.service.update_member_role(
            team_id, member_id, request.user, payload
        )
        return 200, member

    @http_delete(
        "/{{team_id}}/members/{{member_id}}",
        response={{204: None, 403: dict, 404: dict}},
    )
    @log_api_call()
    def remove_member(self, request, team_id: UUID, member_id: UUID):
        """Remove a member from a team the user leads."""
        self.service.remove_member(team_id, member_id, request.user)
        return 204, None
'''

TEAM_ADMIN_TEMPLATE = '''"""Team admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ["name", "member_count", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()


@admin.register(TeamMember)
class TeamMemberAdmin(ModelAdmin):
    list_display = ["user", "team", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email", "team__name"]
    readonly_fields = ["created_at", "updated_at"]
'''

# One smoke/permission test file: member list, non-member 404, non-lead 403
# and invalid payload 422.
TEAM_TESTS_TEMPLATE = '''"""Smoke and permission tests for the {app_name} API."""

import pytest

{first_party_imports}


def make_team(user, role=TeamRole.LEAD):
    team = Team.objects.create(name="Core")
    TeamMember.objects.create(team=team, user=user, role=role)
    return team


@pytest.mark.django_db
class TestTeamAPI:
    """Smoke and permission tests for team endpoints."""

    def test_list_as_member_returns_200(self, authenticated_client):
        client, user = authenticated_client
        team = make_team(user)
        make_team(UserFactory())
        response = client.get("/api/teams/")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [str(team.id)]

    def test_non_member_cannot_read_team(self, authenticated_client):
        client, _ = authenticated_client
        team = make_team(UserFactory())
        response = client.get(f"/api/teams/{{team.id}}")
        assert response.status_code == 404

    def test_member_who_is_not_lead_cannot_update_team(self, authenticated_client):
        client, user = authenticated_client
        team = make_team(user, role=TeamRole.MEMBER)
        response = client.put(
            f"/api/teams/{{team.id}}",
            {{"name": "Renamed"}},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_create_with_invalid_payload_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post("/api/teams/", {{}}, content_type="application/json")
        assert_validation_error(response, field="name")
'''

SCHEMA_NAMES = [
    "TeamSchema",
    "CreateTeamSchema",
    "UpdateTeamSchema",
    "TeamMemberSchema",
    "AddTeamMemberSchema",
    "UpdateTeamMemberSchema",
]


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

        self.create_django_app()
        self.remove_scaffold()
        self._generate_models()
        self._generate_schemas()
        self._generate_services()
        self._generate_controllers()
        self._generate_admin()
        self._generate_tests()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "TeamController")
        self.create_migration()

        print("Team feature generated successfully!")

    def _generate_models(self) -> None:
        """Generate team models."""
        app = self.app_name
        self.create_file(self.app_path / "models" / "team.py", TEAM_MODELS_TEMPLATE)
        self.create_file(
            self.app_path / "models" / "__init__.py",
            package_init((f"{app}.models.team", ["Team", "TeamMember", "TeamRole"])),
        )

    def _generate_schemas(self) -> None:
        """Generate team schemas."""
        app = self.app_name
        first_party_imports = import_block(
            "from core.schemas.base_schema import CamelCaseSchema",
            from_import(f"{app}.models", "TeamRole"),
        )
        self.create_file(
            self.app_path / "schemas" / "team_schema.py",
            TEAM_SCHEMAS_TEMPLATE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            self.app_path / "schemas" / "__init__.py",
            package_init((f"{app}.schemas.team_schema", SCHEMA_NAMES)),
        )

    def _generate_services(self) -> None:
        """Generate the membership-scoped team service."""
        app = self.app_name
        first_party_imports = import_block(
            from_import("api.exceptions", "APIPermissionError", "ConflictError"),
            from_import(f"{app}.models", "Team", "TeamMember", "TeamRole"),
            from_import(
                f"{app}.schemas",
                "AddTeamMemberSchema",
                "CreateTeamSchema",
                "UpdateTeamMemberSchema",
                "UpdateTeamSchema",
            ),
        )
        self.create_file(
            self.app_path / "services" / "team_service.py",
            TEAM_SERVICE_TEMPLATE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            self.app_path / "services" / "__init__.py",
            package_init((f"{app}.services.team_service", ["TeamService"])),
        )

    def _generate_controllers(self) -> None:
        """Generate the team controller."""
        app = self.app_name
        first_party_imports = import_block(
            "from api.decorators import log_api_call",
            from_import(f"{app}.schemas", *SCHEMA_NAMES),
            from_import(f"{app}.services", "TeamService"),
        )
        self.create_file(
            self.app_path / "controllers" / "team_controller.py",
            TEAM_CONTROLLER_TEMPLATE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            self.app_path / "controllers" / "__init__.py",
            package_init((f"{app}.controllers.team_controller", ["TeamController"])),
        )

    def _generate_admin(self) -> None:
        """Generate team admin."""
        app = self.app_name
        self.create_file(
            self.app_path / "admin" / "team_admin.py",
            TEAM_ADMIN_TEMPLATE.format(
                first_party_imports=from_import(f"{app}.models", "Team", "TeamMember")
            ),
        )
        self.create_file(
            self.app_path / "admin" / "__init__.py",
            package_init((f"{app}.admin.team_admin", ["TeamAdmin", "TeamMemberAdmin"])),
        )

    def _generate_tests(self) -> None:
        """Generate the team smoke and permission tests."""
        app = self.app_name
        first_party_imports = import_block(
            "from core.tests.factories import UserFactory",
            from_import(f"{app}.models", "Team", "TeamMember", "TeamRole"),
            "from tests.utils.assertions import assert_validation_error",
        )
        self.create_file(
            self.app_path / "tests" / "test_team.py",
            TEAM_TESTS_TEMPLATE.format(
                app_name=app, first_party_imports=first_party_imports
            ),
        )

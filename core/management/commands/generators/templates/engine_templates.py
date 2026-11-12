"""Templates for the engine generator: an engine and its module apps.

Each module is a Django app at ``engines/<engine>/<module>``. Modules keep
their layers apart: repositories return DTOs, services take schemas and
return DTOs, controllers return DTOs and response schemas serialize them.
"""

# Engine package README: the layout and the boundary rules.
ENGINE_README_TEMPLATE = """# {engine_title} engine

Bounded context for the {engine} domain. It groups these module apps:

{module_list}

## Layout

    engines/{engine}/
        services/   Engine-level composition of module services
        <module>/   Django app: models, repositories, dtos, services,
                    schemas, controllers, admin, migrations, tests

## Rules

- A module imports another module only through its `services` and `dtos`
  packages. It never imports another module's models or repositories.
- Code under the engine's `services/` composes module services. Put
  cross-module flows there.
- Refer to another engine's data by id only.
- Controllers return DTOs. Response schemas serialize them.
"""

# Engine-level service: composes the module services of one engine.
ENGINE_SERVICE_TEMPLATE = '''"""Composes the module services of the {engine} engine.

Put cross-module flows here. Modules never import each other's models or
repositories.
"""

{first_party_imports}


class {engine_class}EngineService:
    """Entry point to the module services of the {engine} engine."""

    def __init__(self):
{attributes}
'''

APPS_TEMPLATE = '''"""{module_title} module of the {engine} engine."""

from django.apps import AppConfig


class {module_class}Config(AppConfig):
    """App config for {app_name}."""

    name = "{app_name}"
    label = "{app_label}"
    verbose_name = "{tag}"
'''

MODEL_TEMPLATE = '''"""{model_name} model of the {engine} engine."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class {model_name}(AbstractBaseModel):
    """A {model_snake} owned by one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "{model_name}"
        verbose_name_plural = "{tag}"

    def __str__(self):
        return self.title
'''

DTO_TEMPLATE = '''"""{model_name} data transfer object of the {engine} engine."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class {model_name}DTO:
    """Read-only view of one {model_snake}. It crosses module boundaries."""

    id: UUID
    owner_id: UUID
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
'''

# Repository: the only layer that touches the ORM. It returns DTOs or None.
REPOSITORY_TEMPLATE = '''"""Persistence for {model_name}. Returns DTOs, never model instances."""

from uuid import UUID

{first_party_imports}


class {model_name}Repository:
    """Owner-scoped queries for {model_name}. Only active rows are visible."""

    def list_for_owner(self, owner_id: UUID) -> list[{model_name}DTO]:
        """Return the owner's active {route}, newest first."""
        items = self._active(owner_id).order_by("-created_at")
        return [self._to_dto(item) for item in items]

    def get_for_owner(self, item_id: UUID, owner_id: UUID) -> {model_name}DTO | None:
        """Return one active item of the owner, or None."""
        item = self._active(owner_id).filter(id=item_id).first()
        return None if item is None else self._to_dto(item)

    def create(self, owner_id: UUID, **fields: str) -> {model_name}DTO:
        """Create an item owned by ``owner_id``."""
        item = {model_name}.objects.create(user_id=owner_id, **fields)
        return self._to_dto(item)

    def update(
        self,
        item_id: UUID,
        owner_id: UUID,
        **fields: str,
    ) -> {model_name}DTO | None:
        """Set the fields on one active item of the owner, or return None."""
        item = self._active(owner_id).filter(id=item_id).first()
        if item is None:
            return None
        for key, value in fields.items():
            setattr(item, key, value)
        item.save()
        return self._to_dto(item)

    def delete(self, item_id: UUID, owner_id: UUID) -> bool:
        """Soft-delete one active item of the owner. Return False if none."""
        item = self._active(owner_id).filter(id=item_id).first()
        if item is None:
            return False
        item.soft_delete()
        return True

    @staticmethod
    def _active(owner_id: UUID):
        return {model_name}.objects.filter(user_id=owner_id, is_active=True)

    @staticmethod
    def _to_dto(item: {model_name}) -> {model_name}DTO:
        return {model_name}DTO(
            id=item.id,
            owner_id=item.user_id,
            title=item.title,
            description=item.description,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
'''

# Service: takes schemas, passes plain values to the repository, returns DTOs.
SERVICE_TEMPLATE = '''"""Business logic for {model_name}. Every call is scoped to the owner."""

from uuid import UUID

{first_party_imports}


class {model_name}Service:
    """Owner-scoped CRUD for {model_name}. Takes schemas, returns DTOs."""

    def __init__(self):
        self.repository = {model_name}Repository()

    def list_for_owner(self, owner_id: UUID) -> list[{model_name}DTO]:
        """Return the owner's {route}, newest first."""
        return self.repository.list_for_owner(owner_id)

    def get_for_owner(self, item_id: UUID, owner_id: UUID) -> {model_name}DTO:
        """Return one of the owner's {route}. Raise NotFoundError otherwise."""
        item = self.repository.get_for_owner(item_id, owner_id)
        if item is None:
            raise NotFoundError("{model_name} not found")
        return item

{create_def}
        """Create one {model_snake} owned by the user."""
        return self.repository.create(owner_id, **payload.model_dump_fields())

{update_def}
        """Update one of the owner's {route}. Raise NotFoundError otherwise."""
        item = self.repository.update(item_id, owner_id, **payload.model_dump_fields())
        if item is None:
            raise NotFoundError("{model_name} not found")
        return item

    def delete(self, item_id: UUID, owner_id: UUID) -> None:
        """Soft-delete one of the owner's {route}. Raise NotFoundError otherwise."""
        if not self.repository.delete(item_id, owner_id):
            raise NotFoundError("{model_name} not found")
'''

SCHEMA_TEMPLATE = '''"""{model_name} schemas of the {engine} engine."""

from datetime import datetime
from uuid import UUID

from core.schemas.base_schema import CamelCaseSchema


class {model_name}Schema(CamelCaseSchema):
    """Response schema. ``from_attributes`` reads it from a DTO."""

    id: UUID
    title: str
    description: str
    created_at: datetime
    updated_at: datetime


class Create{model_name}Schema(CamelCaseSchema):
    title: str
    description: str


class Update{model_name}Schema(CamelCaseSchema):
    title: str
    description: str
'''

# Controller: JWTAuth on the class, a thin handler per route, the owner id
# passed to the service, and DTOs returned for the response schema to read.
CONTROLLER_TEMPLATE = '''"""{model_name} controller of the {engine} engine. Scoped to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/{engine}/{route}", tags=["{tag}"], auth=JWTAuth())
class {controller_class}:
    """CRUD endpoints for the authenticated user's {route}.

    Put static paths before the first /{{item_id}} handler.
    """

    def __init__(self):
        self.service = {model_name}Service()

    @http_get("/", response={{200: list[{model_name}Schema]}})
    @log_api_call()
    def list_{route}(self, request):
        """List the user's {route}."""
        return 200, self.service.list_for_owner(request.user.id)

    @http_post("/", response={{201: {model_name}Schema}})
    @log_api_call(include_payload=True)
{create_def}
        """Create one {model_snake} for the user."""
        return 201, self.service.create(request.user.id, payload)

    @http_get("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call()
    def get_{model_snake}(self, request, item_id: UUID):
        """Get one of the user's {route}."""
        return 200, self.service.get_for_owner(item_id, request.user.id)

    @http_put("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call(include_payload=True)
{update_def}
        """Update one of the user's {route}."""
        return 200, self.service.update(item_id, request.user.id, payload)

    @http_delete("/{{item_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_{model_snake}(self, request, item_id: UUID):
        """Delete one of the user's {route}."""
        self.service.delete(item_id, request.user.id)
        return 204, None
'''

ADMIN_TEMPLATE = '''"""{model_name} admin of the {engine} engine."""

from django.contrib import admin

{first_party_imports}


@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    """List and search view for {model_name}."""

    list_display = ("title", "user", "created_at")
    search_fields = ("title",)
'''

# Boundary tests only (AGENTS.md section 10): authentication and ownership.
BOUNDARY_TESTS_TEMPLATE = '''"""Boundary tests for the {app_name} module: authentication and ownership."""

import pytest

{first_party_imports}


@pytest.mark.django_db
class Test{model_name}Boundary:
    """Unauthenticated and cross-owner requests to {model_name} endpoints."""

    def test_unauthenticated_list_returns_401(self, api_client):
        response = api_client.get("/api/{engine}/{route}/")
        assert response.status_code == 401

    def test_other_user_cannot_read_item(self, authenticated_client):
        client, _ = authenticated_client
        other = UserFactory()
        item = {model_name}.objects.create(user=other, title="Theirs")
        response = client.get(f"/api/{engine}/{route}/{{item.id}}")
        assert response.status_code == 404
'''

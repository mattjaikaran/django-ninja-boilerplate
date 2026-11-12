"""Templates shared by startapp_extended and the api_endpoint generator."""

from core.management.commands.generators.codegen import (
    ResourceNames,
    from_import,
    import_block,
    method_def,
)

APP_LAYERS = ("service", "repository", "dto")
DEFAULT_LAYERS = "repository"
# Extra package directories that each layer adds to a generated app.
LAYER_PACKAGES = {
    "service": (),
    "repository": ("repositories",),
    "dto": ("repositories", "dtos"),
}

# Owned resource behind SERVICE_TEMPLATE: the service scopes every query on
# the ``user`` foreign key.
MODEL_TEMPLATE = '''"""{model_name} model."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class {model_name}(AbstractBaseModel):
    """A {model_snake} owned by one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="{route}"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "{model_name}"
        verbose_name_plural = "{tag}"

    def __str__(self):
        return self.title
'''

SCHEMA_TEMPLATE = '''"""{model_name} schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from core.schemas.base_schema import CamelCaseSchema


class {model_name}Schema(CamelCaseSchema):
    id: str
    title: str
    description: str
    created_at: str
    updated_at: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Serialize the UUID primary key as a string."""
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Serialize timestamps as ISO 8601 strings."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class Create{model_name}Schema(CamelCaseSchema):
    title: str
    description: str


class Update{model_name}Schema(CamelCaseSchema):
    title: str
    description: str
'''

# Owner-scoped CRUD service behind CONTROLLER_TEMPLATE. Every query filters on
# the owner, so another user's item is a 404.
SERVICE_TEMPLATE = '''"""Business logic for {model_name}. Every query is scoped to the owner."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from {app_name}.models import {model_name}
{schema_import}


class {model_name}Service:
    """Owner-scoped CRUD for {model_name}."""

    def list_for_user(self, user: Any) -> QuerySet[{model_name}]:
        """Return the items that belong to the user, newest first."""
        return {model_name}.objects.filter(user=user).order_by("-created_at")

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name}:
        """Return one item owned by the user. Raise Http404 for any other item."""
        return get_object_or_404({model_name}, id=item_id, user=user)

{create_def}
        """Create an item owned by the user."""
        return {model_name}.objects.create(user=user, **payload.model_dump_fields())

{update_def}
        """Apply the set fields of the payload to an item owned by the user."""
        item = self.get_for_user(item_id, user)
        for key, value in payload.model_dump_fields(exclude_unset=True).items():
            setattr(item, key, value)
        item.save()
        return item

    def delete(self, item_id: UUID, user: Any) -> None:
        """Delete an item owned by the user."""
        self.get_for_user(item_id, user).delete()
'''


REPOSITORY_TEMPLATE = '''"""Data access for {model_name}. Every query is scoped to the owner."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from {app_name}.models import {model_name}


class {model_name}Repository:
    """Owner-scoped queries for {model_name}."""

    def list_for_user(self, user: Any) -> QuerySet[{model_name}]:
        """Return the items that belong to the user, newest first."""
        return {model_name}.objects.filter(user=user).order_by("-created_at")

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name} | None:
        """Return one item owned by the user, or None."""
        return {model_name}.objects.filter(user=user, id=item_id).first()

    def create(self, user: Any, **fields: Any) -> {model_name}:
        """Create an item owned by the user."""
        return {model_name}.objects.create(user=user, **fields)

    def update(self, item: {model_name}, **fields: Any) -> {model_name}:
        """Set the given fields on an item and save it."""
        for key, value in fields.items():
            setattr(item, key, value)
        item.save()
        return item

    def delete(self, item: {model_name}) -> None:
        """Delete an item."""
        item.delete()
'''

REPOSITORY_SERVICE_TEMPLATE = '''"""Business logic for {model_name}. Every query is scoped to the owner."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.http import Http404

{first_party_imports}


class {model_name}Service:
    """Owner-scoped CRUD for {model_name}."""

    def __init__(self, repository: {model_name}Repository | None = None) -> None:
        """Initialise the service with an optional injected repository."""
        self.repository = repository or {model_name}Repository()

    def list_for_user(self, user: Any) -> QuerySet[{model_name}]:
        """Return the items that belong to the user, newest first."""
        return self.repository.list_for_user(user)

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name}:
        """Return one item owned by the user. Raise Http404 for any other item."""
        item = self.repository.get_for_user(item_id, user)
        if item is None:
            raise Http404("{model_name} not found")
        return item

{create_def}
        """Create an item owned by the user."""
        return self.repository.create(user, **payload.model_dump_fields())

{update_def}
        """Apply the set fields of the payload to an item owned by the user."""
        item = self.get_for_user(item_id, user)
        return self.repository.update(
            item, **payload.model_dump_fields(exclude_unset=True)
        )

    def delete(self, item_id: UUID, user: Any) -> None:
        """Delete an item owned by the user."""
        self.repository.delete(self.get_for_user(item_id, user))
'''

DTO_TEMPLATE = '''"""Read model for {model_name}. Plain data, no ORM objects."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class {model_name}DTO:
    """A {model_snake} as the service layer sees it."""

    id: UUID
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
'''

DTO_REPOSITORY_TEMPLATE = '''"""Data access for {model_name} that returns DTOs, never ORM rows."""

from typing import Any
from uuid import UUID

from {app_name}.dtos import {model_name}DTO
from {app_name}.models import {model_name}


class {model_name}Repository:
    """Owner-scoped queries for {model_name}. Every method returns DTOs."""

    def list_for_user(self, user: Any) -> list[{model_name}DTO]:
        """Return the user's items as DTOs, newest first."""
        items = {model_name}.objects.filter(user=user).order_by("-created_at")
        return [self._to_dto(item) for item in items]

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name}DTO | None:
        """Return one of the user's items as a DTO, or None."""
        item = {model_name}.objects.filter(user=user, id=item_id).first()
        return self._to_dto(item) if item else None

    def create(self, user: Any, **fields: Any) -> {model_name}DTO:
        """Create an item owned by the user."""
        return self._to_dto({model_name}.objects.create(user=user, **fields))

{update_def}
        """Set the given fields on the user's item. Return None when it is missing."""
        item = {model_name}.objects.filter(user=user, id=item_id).first()
        if item is None:
            return None
        for key, value in fields.items():
            setattr(item, key, value)
        item.save()
        return self._to_dto(item)

    def delete(self, item_id: UUID, user: Any) -> bool:
        """Delete the user's item. Return False when no item matched."""
        deleted, _ = {model_name}.objects.filter(user=user, id=item_id).delete()
        return deleted > 0

    @staticmethod
    def _to_dto(item: {model_name}) -> {model_name}DTO:
        """Map a model row to its DTO."""
        return {model_name}DTO(
            id=item.id,
            title=item.title,
            description=item.description,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
'''

DTO_SERVICE_TEMPLATE = '''"""Business logic for {model_name}. Every query is scoped to the owner."""

from typing import Any
from uuid import UUID

from django.http import Http404

{first_party_imports}


class {model_name}Service:
    """Owner-scoped CRUD for {model_name}."""

    def __init__(self, repository: {model_name}Repository | None = None) -> None:
        """Initialise the service with an optional injected repository."""
        self.repository = repository or {model_name}Repository()

    def list_for_user(self, user: Any) -> list[{model_name}DTO]:
        """Return the items that belong to the user, newest first."""
        return self.repository.list_for_user(user)

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name}DTO:
        """Return one item owned by the user. Raise Http404 for any other item."""
        item = self.repository.get_for_user(item_id, user)
        if item is None:
            raise Http404("{model_name} not found")
        return item

{create_def}
        """Create an item owned by the user."""
        return self.repository.create(user, **payload.model_dump_fields())

{update_def}
        """Apply the set fields of the payload to an item owned by the user."""
        item = self.repository.update(
            item_id, user, **payload.model_dump_fields(exclude_unset=True)
        )
        if item is None:
            raise Http404("{model_name} not found")
        return item

    def delete(self, item_id: UUID, user: Any) -> None:
        """Delete an item owned by the user."""
        if not self.repository.delete(item_id, user):
            raise Http404("{model_name} not found")
'''


def _service_defs(names: ResourceNames, item: str) -> dict[str, str]:
    """Return the create and update signatures for a service that returns ``item``."""
    model = names.model_name
    return {
        "create_def": method_def(
            "create", f"self, user: Any, payload: Create{model}Schema", item
        ),
        "update_def": method_def(
            "update",
            f"self, item_id: UUID, user: Any, payload: Update{model}Schema",
            item,
        ),
    }


def render_service(names: ResourceNames, layers: str) -> str:
    """Render the service for one resource in the shape ``layers`` selects."""
    model = names.model_name
    schemas = from_import(
        f"{names.app_name}.schemas", f"Create{model}Schema", f"Update{model}Schema"
    )
    if layers == "service":
        return SERVICE_TEMPLATE.format(
            schema_import=schemas,
            **_service_defs(names, model),
            **names.context(),
        )
    if layers == "repository":
        template, item = REPOSITORY_SERVICE_TEMPLATE, model
        imports = import_block(
            from_import(f"{names.app_name}.models", model),
            from_import(f"{names.app_name}.repositories", f"{model}Repository"),
            schemas,
        )
    else:
        template, item = DTO_SERVICE_TEMPLATE, f"{model}DTO"
        imports = import_block(
            from_import(f"{names.app_name}.dtos", f"{model}DTO"),
            from_import(f"{names.app_name}.repositories", f"{model}Repository"),
            schemas,
        )
    return template.format(
        first_party_imports=imports,
        **_service_defs(names, item),
        **names.context(),
    )


def render_repository(names: ResourceNames, layers: str) -> str:
    """Render the repository for one resource. The dto shape returns DTOs."""
    if layers == "repository":
        return REPOSITORY_TEMPLATE.format(**names.context())
    update_def = method_def(
        "update",
        "self, item_id: UUID, user: Any, **fields: Any",
        f"{names.model_name}DTO | None",
    )
    return DTO_REPOSITORY_TEMPLATE.format(update_def=update_def, **names.context())


def render_dto(names: ResourceNames) -> str:
    """Render the DTO dataclass for one resource."""
    return DTO_TEMPLATE.format(**names.context())


# AGENTS.md section 08: JWTAuth on the controller, a thin handler per route
# that calls the owner-scoped service, no try/except around lookups, and
# static paths before every /{item_id} handler.
CONTROLLER_TEMPLATE = '''"""{model_name} controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/{route}", tags=["{tag}"], auth=JWTAuth())
class {model_name}Controller:
    """CRUD endpoints for the authenticated user's {route}.

    Put static paths before the first /{{item_id}} handler.
    """

{init_method}

    @http_get("/", response={{200: list[{model_name}Schema]}})
    @log_api_call()
    def list_{route}(self, request):
        """List the user's {route}."""
        return 200, self.service.list_for_user(request.user)

    @http_post("/", response={{201: {model_name}Schema}})
    @log_api_call(include_payload=True)
{create_def}
        """Create a {model_snake} for the user."""
        return 201, self.service.create(request.user, payload)

    @http_get("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call()
    def get_{model_snake}(self, request, item_id: UUID):
        """Get one of the user's {route}."""
        return 200, self.service.get_for_user(item_id, request.user)

    @http_put("/{{item_id}}", response={{200: {model_name}Schema, 404: dict}})
    @log_api_call(include_payload=True)
{update_def}
        """Update one of the user's {route}."""
        return 200, self.service.update(item_id, request.user, payload)

    @http_delete("/{{item_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_{model_snake}(self, request, item_id: UUID):
        """Delete one of the user's {route}."""
        self.service.delete(item_id, request.user)
        return 204, None
'''


def render_controller(names: ResourceNames, layers: str) -> str:
    """Render CONTROLLER_TEMPLATE with its first-party imports in isort order."""
    model = names.model_name
    first_party_imports = import_block(
        "from api.decorators import log_api_call",
        from_import(
            f"{names.app_name}.schemas",
            f"{model}Schema",
            f"Create{model}Schema",
            f"Update{model}Schema",
        ),
        from_import(f"{names.app_name}.services", f"{model}Service"),
    )
    if layers == "service":
        init_method = (
            f"    def __init__(self):\n        self.service = {model}Service()"
        )
    else:
        init_method = (
            f"    def __init__(self, service: {model}Service):\n"
            f'        """Store the injected {model}Service."""\n'
            "        self.service = service"
        )
    return CONTROLLER_TEMPLATE.format(
        first_party_imports=first_party_imports,
        init_method=init_method,
        create_def=method_def(
            f"create_{names.model_snake}",
            f"self, request, payload: Create{model}Schema",
        ),
        update_def=method_def(
            f"update_{names.model_snake}",
            f"self, request, item_id: UUID, payload: Update{model}Schema",
        ),
        **names.context(),
    )


# Generated features get ONE smoke/permission test file. Playwright journeys in
# the frontend verify the feature itself; see docs/product/README.md.
API_ENDPOINT_TESTS_TEMPLATE = '''"""Smoke and permission tests for the {app_name} API."""

import pytest

{first_party_imports}


@pytest.mark.django_db
class Test{model_name}API:
    """Smoke and permission tests for {model_name} endpoints."""

    def test_list_as_owner_returns_200(self, authenticated_client):
        client, user = authenticated_client
        {model_name}.objects.create(user=user, title="Mine")
        response = client.get("/api/{route}/")
        assert response.status_code == 200

    def test_other_user_cannot_read_item(self, authenticated_client):
        client, _ = authenticated_client
        other = UserFactory()
        obj = {model_name}.objects.create(user=other, title="Theirs")
        response = client.get(f"/api/{route}/{{obj.id}}")
        assert response.status_code == 404

    def test_create_with_invalid_payload_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post("/api/{route}/", {{}}, content_type="application/json")
        assert_validation_error(response, field="title")
'''


def render_api_endpoint_tests(names: ResourceNames) -> str:
    """Render API_ENDPOINT_TESTS_TEMPLATE with its imports in isort order."""
    first_party_imports = import_block(
        "from core.tests.factories import UserFactory",
        from_import(f"{names.app_name}.models", names.model_name),
        "from tests.utils.assertions import assert_validation_error",
    )
    return API_ENDPOINT_TESTS_TEMPLATE.format(
        first_party_imports=first_party_imports, **names.context()
    )


def render_app_files(names: ResourceNames, layers: str) -> dict[str, str]:
    """Return the module files for one app, keyed by path under the app.

    ``layers`` picks the data-access shape. ``service`` keeps one owner-scoped
    service over the ORM. ``repository`` adds a repository that the service
    calls. ``dto`` makes the repository return frozen DTOs.
    """
    if layers not in APP_LAYERS:
        msg = f"layers must be one of {', '.join(APP_LAYERS)}, not {layers!r}"
        raise ValueError(msg)
    snake = names.model_snake
    files = {
        f"models/{snake}.py": MODEL_TEMPLATE.format(**names.context()),
        f"schemas/{snake}_schema.py": SCHEMA_TEMPLATE.format(**names.context()),
        f"services/{snake}_service.py": render_service(names, layers),
        f"controllers/{snake}_controller.py": render_controller(names, layers),
        f"tests/test_{snake}.py": render_api_endpoint_tests(names),
    }
    if layers != "service":
        files[f"repositories/{snake}_repository.py"] = render_repository(names, layers)
    if layers == "dto":
        files[f"dtos/{snake}_dto.py"] = render_dto(names)
    return files

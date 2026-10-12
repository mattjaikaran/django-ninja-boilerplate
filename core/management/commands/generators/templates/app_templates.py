"""Templates shared by startapp_extended and the api_endpoint generator."""

from core.management.commands.generators.codegen import (
    ResourceNames,
    from_import,
    import_block,
    method_def,
)

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


def render_service(names: ResourceNames) -> str:
    """Render SERVICE_TEMPLATE for one resource."""
    model = names.model_name
    schema_import = from_import(
        f"{names.app_name}.schemas", f"Create{model}Schema", f"Update{model}Schema"
    )
    return SERVICE_TEMPLATE.format(
        schema_import=schema_import,
        create_def=method_def(
            "create", f"self, user: Any, payload: Create{model}Schema", model
        ),
        update_def=method_def(
            "update",
            f"self, item_id: UUID, user: Any, payload: Update{model}Schema",
            model,
        ),
        **names.context(),
    )


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

    def __init__(self):
        self.service = {model_name}Service()

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


def render_controller(names: ResourceNames) -> str:
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
    return CONTROLLER_TEMPLATE.format(
        first_party_imports=first_party_imports,
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

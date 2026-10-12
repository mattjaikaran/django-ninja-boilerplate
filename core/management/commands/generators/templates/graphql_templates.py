"""Templates for the GraphQL (Strawberry) feature generator.

Each template is verbatim code. ``__APP__`` stands for the app name.
Resolvers hold no ORM code: they call ``GraphQLUserService``, which scopes
every query to the viewer or to an explicit staff check.
"""

GRAPHQL_TYPES_TEMPLATE = '''"""GraphQL types for __APP__."""

from datetime import datetime
from typing import Any, Self
from uuid import UUID

import strawberry


@strawberry.type
class UserType:
    """GraphQL type for the User model."""

    id: UUID
    email: str
    username: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @classmethod
    def from_model(cls, user: Any) -> Self:
        """Build the type from a User instance."""
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.date_joined,
            updated_at=user.updated_at,
        )


@strawberry.type
class PageInfo:
    """Pagination information for relay-style connections."""

    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None = None
    end_cursor: str | None = None


@strawberry.type
class ErrorType:
    """Standard error type for mutation responses."""

    field: str
    message: str


@strawberry.type
class SuccessType:
    """Standard success response type."""

    success: bool
    message: str
'''

GRAPHQL_CONTEXT_TEMPLATE = '''"""GraphQL context for __APP__.

The context gives every resolver request-scoped data through ``info.context``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from strawberry.django.context import StrawberryDjangoContext

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpRequest
    from strawberry.django.views import TemporalHttpResponse

    from core.models import User


@dataclass
class GraphQLContext(StrawberryDjangoContext):
    """GraphQL context with typed access to the current user."""

    @property
    def user(self) -> User | AnonymousUser:
        """Return the authenticated user or AnonymousUser."""
        return self.request.user

    @property
    def is_authenticated(self) -> bool:
        """Return True when the request carries an authenticated user."""
        return self.request.user.is_authenticated


def get_context(request: HttpRequest, response: TemporalHttpResponse) -> GraphQLContext:
    """Create the GraphQL context for one request."""
    return GraphQLContext(request=request, response=response)
'''

GRAPHQL_PERMISSIONS_TEMPLATE = '''"""Permission classes for the __APP__ GraphQL resolvers."""

from typing import Any

from strawberry.permission import BasePermission
from strawberry.types import Info


class IsAuthenticated(BasePermission):
    """Allow only a user that the GraphQL view authenticated."""

    message = "Authentication required"

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        """Return True for an authenticated user."""
        return info.context.is_authenticated


class IsStaff(BasePermission):
    """Allow only an authenticated staff user."""

    message = "Staff access required"

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        """Return True for an authenticated staff user."""
        return info.context.is_authenticated and info.context.user.is_staff
'''

GRAPHQL_USER_SERVICE_TEMPLATE = '''"""User data for the __APP__ GraphQL resolvers.

Every query is scoped to the viewer: staff see every user, other users see
only themselves.
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from api.exceptions import APIPermissionError, ValidationError

User = get_user_model()

# Largest page the users query returns.
MAX_PAGE_SIZE = 100


class GraphQLUserService:
    """User reads and profile writes for GraphQL resolvers."""

    def _visible(self, viewer: Any) -> QuerySet:
        """Return the users the viewer may see, oldest first."""
        if viewer.is_staff:
            return User.objects.order_by("date_joined")
        return User.objects.filter(pk=viewer.pk)

    def get_visible(self, viewer: Any, user_id: str) -> Any | None:
        """Return the user when the viewer may see it, else None."""
        return self._visible(viewer).filter(pk=user_id).first()

    def list_users(self, viewer: Any, limit: int, offset: int) -> list[Any]:
        """Return one page of users. Staff only."""
        if not viewer.is_staff:
            raise APIPermissionError("Staff access required")
        if not 1 <= limit <= MAX_PAGE_SIZE or offset < 0:
            msg = f"limit must be 1 to {MAX_PAGE_SIZE} and offset must be 0 or more"
            raise ValidationError(msg)
        return list(self._visible(viewer)[offset : offset + limit])

    def username_taken(self, user: Any, username: str) -> bool:
        """Return True when another user has the username."""
        return User.objects.exclude(pk=user.pk).filter(username=username).exists()

    def update_profile(self, user: Any, **fields: str | None) -> Any:
        """Save the fields that are not None on the user."""
        changed = {name: value for name, value in fields.items() if value is not None}
        for name, value in changed.items():
            setattr(user, name, value)
        if changed:
            user.save(update_fields=[*changed, "updated_at"])
        return user

    def deactivate(self, user: Any) -> None:
        """Deactivate the user's account."""
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
'''

GRAPHQL_QUERIES_TEMPLATE = '''"""GraphQL queries for __APP__. Resolvers call GraphQLUserService."""

import strawberry
from strawberry.types import Info

from .context import GraphQLContext
from .permissions import IsAuthenticated, IsStaff
from .types import UserType
from .user_service import GraphQLUserService


@strawberry.type
class Query:
    """Root query type. Every field requires an authenticated user."""

    @strawberry.field(permission_classes=[IsAuthenticated])
    def me(self, info: Info[GraphQLContext, None]) -> UserType:
        """Return the authenticated user."""
        return UserType.from_model(info.context.user)

    @strawberry.field(permission_classes=[IsAuthenticated])
    def user(
        self, info: Info[GraphQLContext, None], id: strawberry.ID
    ) -> UserType | None:
        """Return a user the viewer may see. Others are null."""
        user = GraphQLUserService().get_visible(info.context.user, id)
        return UserType.from_model(user) if user is not None else None

    @strawberry.field(permission_classes=[IsStaff])
    def users(
        self, info: Info[GraphQLContext, None], limit: int = 10, offset: int = 0
    ) -> list[UserType]:
        """Return one page of users, oldest first. Staff only."""
        users = GraphQLUserService().list_users(
            info.context.user, limit=limit, offset=offset
        )
        return [UserType.from_model(user) for user in users]
'''

GRAPHQL_MUTATIONS_TEMPLATE = '''"""GraphQL mutations for __APP__. Resolvers call GraphQLUserService."""

import strawberry
from strawberry.types import Info

from .context import GraphQLContext
from .permissions import IsAuthenticated
from .types import ErrorType, SuccessType, UserType
from .user_service import GraphQLUserService


@strawberry.input
class UpdateUserInput:
    """Input type for updating the user's profile."""

    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


@strawberry.type
class UpdateUserPayload:
    """Payload returned from the updateUser mutation."""

    user: UserType | None = None
    errors: list[ErrorType] | None = None


@strawberry.type
class Mutation:
    """Root mutation type. Every mutation requires an authenticated user."""

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_user(
        self, info: Info[GraphQLContext, None], input: UpdateUserInput
    ) -> UpdateUserPayload:
        """Update the authenticated user's profile."""
        service = GraphQLUserService()
        user = info.context.user
        if input.username is not None and service.username_taken(user, input.username):
            error = ErrorType(field="username", message="Username already taken")
            return UpdateUserPayload(errors=[error])
        user = service.update_profile(
            user,
            first_name=input.first_name,
            last_name=input.last_name,
            username=input.username,
        )
        return UpdateUserPayload(user=UserType.from_model(user))

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def delete_account(
        self, info: Info[GraphQLContext, None], confirm: bool = False
    ) -> SuccessType:
        """Deactivate the authenticated user's account. Requires confirm=true."""
        if not confirm:
            return SuccessType(
                success=False,
                message="Please confirm deletion by setting confirm=true",
            )
        GraphQLUserService().deactivate(info.context.user)
        return SuccessType(success=True, message="Account deactivated successfully")
'''

GRAPHQL_SCHEMA_TEMPLATE = '''"""GraphQL schema for __APP__: the Query and Mutation types."""

import strawberry
from django.conf import settings
from strawberry.extensions import QueryDepthLimiter

from .mutations import Mutation
from .queries import Query

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[QueryDepthLimiter(max_depth=settings.STRAWBERRY["MAX_QUERY_DEPTH"])],
)
'''

GRAPHQL_INIT_TEMPLATE = '''"""GraphQL package for __APP__, built on Strawberry."""

from .context import GraphQLContext, get_context
from .mutations import Mutation
from .queries import Query
from .schema import schema

__all__ = [
    "GraphQLContext",
    "Mutation",
    "Query",
    "get_context",
    "schema",
]
'''

GRAPHQL_TESTS_TEMPLATE = '''"""Smoke and permission tests for the GraphQL API at /api/graphql/."""

import pytest
from django.test import Client
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory

ME_QUERY = "query { me { id email } }"
USER_QUERY = "query ($id: ID!) { user(id: $id) { id } }"
USERS_QUERY = "query { users { id } }"


@pytest.fixture
def client():
    """A client that enforces CSRF checks, as a real client meets them."""
    return Client(enforce_csrf_checks=True)


def run_query(client, query, token=None, variables=None):
    """POST a GraphQL query, with a bearer token when one is given."""
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(
        "/api/graphql/",
        {"query": query, "variables": variables or {}},
        content_type="application/json",
        **headers,
    )


def token_for(user):
    """Return a JWT access token for the user."""
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db
class TestGraphQLAPI:
    """Smoke and permission tests for the GraphQL queries."""

    def test_me_returns_the_bearer_token_user(self, client, user):
        response = run_query(client, ME_QUERY, token=token_for(user))
        assert response.status_code == 200
        assert response.json()["data"]["me"]["email"] == user.email

    def test_me_rejects_an_invalid_token(self, client):
        body = run_query(client, ME_QUERY, token="invalid").json()
        assert body["data"] is None
        assert body["errors"][0]["message"] == "Authentication required"

    def test_session_post_without_csrf_token_returns_403(self, client, user):
        client.force_login(user)
        response = run_query(client, ME_QUERY)
        assert response.status_code == 403

    def test_users_is_staff_only(self, client, user):
        body = run_query(client, USERS_QUERY, token=token_for(user)).json()
        assert body["data"] is None
        assert body["errors"][0]["message"] == "Staff access required"

    def test_staff_can_list_users(self, client, staff_user, user):
        body = run_query(client, USERS_QUERY, token=token_for(staff_user)).json()
        ids = {row["id"] for row in body["data"]["users"]}
        assert ids == {str(staff_user.pk), str(user.pk)}

    def test_user_cannot_read_another_user(self, client, user):
        variables = {"id": str(UserFactory().pk)}
        response = run_query(client, USER_QUERY, token_for(user), variables)
        assert response.json()["data"]["user"] is None
'''

GRAPHQL_VIEW_TEMPLATE = '''"""JWT-authenticated GraphQL view, mounted at /api/graphql/.

The view authenticates a ``Bearer`` token from the Authorization header with
the same ``JWTAuth`` the REST API uses, then runs the Strawberry view. A
request without a valid token stays anonymous, and resolvers that require
authentication return an error.

The view is ``csrf_exempt`` so that ``ApiCsrfMiddleware`` applies the API rule
under ``/api/``: a request with only header credentials skips the CSRF check,
and a request with an auth or session cookie must pass it.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import AuthenticationFailed
from strawberry.django.views import GraphQLView as BaseGraphQLView

from __APP__.graphql.context import get_context

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from strawberry.django.views import TemporalHttpResponse

    from __APP__.graphql.context import GraphQLContext


@method_decorator(csrf_exempt, name="dispatch")
class JWTAuthenticatedGraphQLView(BaseGraphQLView):
    """GraphQL view that authenticates the user from a JWT bearer token.

    Mount it under /api/ so that ApiCsrfMiddleware checks cookie requests:
        path("api/graphql/", JWTAuthenticatedGraphQLView.as_view(schema=schema))
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Serve the GraphiQL IDE only when STRAWBERRY["GRAPHIQL"] is on."""
        graphiql = "graphiql" if settings.STRAWBERRY["GRAPHIQL"] else None
        kwargs.setdefault("graphql_ide", graphiql)
        super().__init__(*args, **kwargs)

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Authenticate the bearer token, then run the GraphQL view."""
        if getattr(request, "user", None) is None:
            request.user = AnonymousUser()
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # On failure jwt_authenticate leaves the request anonymous.
            with suppress(AuthenticationFailed):
                JWTAuth().jwt_authenticate(request, auth_header.removeprefix("Bearer "))
        return super().dispatch(request, *args, **kwargs)

    def get_context(
        self, request: HttpRequest, response: TemporalHttpResponse
    ) -> GraphQLContext:
        """Return the app's GraphQLContext, which exposes ``user``."""
        return get_context(request, response)


class AsyncJWTAuthenticatedGraphQLView(JWTAuthenticatedGraphQLView):
    """JWT-authenticated GraphQL view for ASGI deployments."""
'''


def render_graphql_files(app_name: str) -> dict[str, str]:
    """Return the app's GraphQL files keyed by path relative to the app."""
    templates = {
        "graphql/types.py": GRAPHQL_TYPES_TEMPLATE,
        "graphql/context.py": GRAPHQL_CONTEXT_TEMPLATE,
        "graphql/permissions.py": GRAPHQL_PERMISSIONS_TEMPLATE,
        "graphql/user_service.py": GRAPHQL_USER_SERVICE_TEMPLATE,
        "graphql/queries.py": GRAPHQL_QUERIES_TEMPLATE,
        "graphql/mutations.py": GRAPHQL_MUTATIONS_TEMPLATE,
        "graphql/schema.py": GRAPHQL_SCHEMA_TEMPLATE,
        "graphql/__init__.py": GRAPHQL_INIT_TEMPLATE,
        "tests/test_graphql.py": GRAPHQL_TESTS_TEMPLATE,
    }
    return {
        path: template.replace("__APP__", app_name)
        for path, template in templates.items()
    }

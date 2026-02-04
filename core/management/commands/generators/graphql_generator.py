"""GraphQL/Strawberry feature generator.

This generator creates an optional GraphQL API setup using Strawberry GraphQL.
It generates schemas, queries, mutations, types, and a JWT-authenticated GraphQL view.
"""

from .base_generator import BaseGenerator


class GraphQLGenerator(BaseGenerator):
    """Generator for GraphQL/Strawberry feature."""

    def __init__(
        self,
        app_name: str,
        minimal: bool = False,
    ):
        """Initialize the GraphQL generator.

        Args:
            app_name: Name of the Django app to add GraphQL to
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal)

    def generate(self) -> None:
        """Generate the GraphQL feature."""
        print(f"Generating GraphQL/Strawberry feature for {self.app_name}...")

        # Create graphql directory structure
        self._create_graphql_directory()

        # Generate GraphQL files
        self._generate_types()
        self._generate_context()
        self._generate_queries()
        self._generate_mutations()
        self._generate_schema()
        self._generate_graphql_init()

        # Generate JWT authenticated view in core
        self._generate_jwt_graphql_view()

        # Update URLs
        self._update_urls_for_graphql()

        # Update settings
        self._update_settings_for_graphql()

        print("GraphQL/Strawberry feature generated successfully!")
        print("\nNext steps:")
        print("1. Install GraphQL dependencies: uv add 'strawberry-graphql[django]'")
        print("2. Run migrations if you added new models")
        print("3. Visit /graphql to access the GraphQL playground")

    def _create_graphql_directory(self) -> None:
        """Create the graphql directory structure."""
        graphql_path = self.app_path / "graphql"
        graphql_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created directory: {graphql_path}")

    def _generate_types(self) -> None:
        """Generate GraphQL types for models."""
        content = f'''"""GraphQL types for {self.app_name} models.

This module defines Strawberry types that map to Django models.
Types are used in queries and mutations to represent data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import strawberry
from strawberry import auto

if TYPE_CHECKING:
    pass


@strawberry.type
class UserType:
    """GraphQL type for User model."""

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
        return f"{{self.first_name}} {{self.last_name}}".strip()


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


# Example: Add your model types here
# @strawberry.django.type(YourModel)
# class YourModelType:
#     id: auto
#     name: auto
#     created_at: auto
'''
        self.create_file(self.app_path / "graphql" / "types.py", content)

    def _generate_context(self) -> None:
        """Generate GraphQL context class."""
        content = f'''"""GraphQL context for {self.app_name}.

This module defines the custom context class that provides
request-scoped data to all resolvers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.auth.models import AnonymousUser
from strawberry.django.context import StrawberryDjangoContext

if TYPE_CHECKING:
    from django.http import HttpRequest

    from core.models import User


@dataclass
class GraphQLContext(StrawberryDjangoContext):
    """Custom GraphQL context with typed user access.

    This context is available in all resolvers via `info.context`.
    It provides type-safe access to the current user and request.
    """

    @property
    def user(self) -> "User | AnonymousUser":
        """Get the current authenticated user or AnonymousUser."""
        return self.request.user

    @property
    def is_authenticated(self) -> bool:
        """Check if the current user is authenticated."""
        return self.request.user.is_authenticated


def get_context(request: "HttpRequest") -> GraphQLContext:
    """Create a GraphQL context from an HTTP request.

    This function is used by the GraphQL view to create the context
    for each request.

    Args:
        request: The Django HTTP request.

    Returns:
        GraphQLContext: The context instance for resolvers.
    """
    return GraphQLContext(request=request)
'''
        self.create_file(self.app_path / "graphql" / "context.py", content)

    def _generate_queries(self) -> None:
        """Generate GraphQL queries."""
        content = f'''"""GraphQL queries for {self.app_name}.

This module defines the Query type with all available queries.
Queries are read-only operations that fetch data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import strawberry
from django.contrib.auth import get_user_model
from strawberry.types import Info

from .types import UserType

if TYPE_CHECKING:
    from .context import GraphQLContext

User = get_user_model()


@strawberry.type
class Query:
    """Root query type for GraphQL API.

    All queries are defined as methods decorated with @strawberry.field.
    """

    @strawberry.field
    def me(self, info: Info["GraphQLContext", None]) -> UserType | None:
        """Get the currently authenticated user.

        Returns:
            The current user if authenticated, None otherwise.
        """
        user = info.context.user
        if not user.is_authenticated:
            return None
        return UserType(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @strawberry.field
    def user(self, info: Info["GraphQLContext", None], id: strawberry.ID) -> UserType | None:
        """Get a user by ID.

        Args:
            id: The user's UUID.

        Returns:
            The user if found, None otherwise.
        """
        if not info.context.is_authenticated:
            return None
        try:
            user = User.objects.get(id=id)
            return UserType(
                id=user.id,
                email=user.email,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        except User.DoesNotExist:
            return None

    @strawberry.field
    def users(
        self,
        info: Info["GraphQLContext", None],
        limit: int = 10,
        offset: int = 0,
    ) -> list[UserType]:
        """Get a paginated list of users.

        Args:
            limit: Maximum number of users to return.
            offset: Number of users to skip.

        Returns:
            List of users.
        """
        if not info.context.is_authenticated:
            return []

        users = User.objects.all()[offset : offset + limit]
        return [
            UserType(
                id=user.id,
                email=user.email,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

    # Add more queries here
    # @strawberry.field
    # def items(self, info: Info) -> list[ItemType]:
    #     return Item.objects.all()
'''
        self.create_file(self.app_path / "graphql" / "queries.py", content)

    def _generate_mutations(self) -> None:
        """Generate GraphQL mutations."""
        content = f'''"""GraphQL mutations for {self.app_name}.

This module defines the Mutation type with all available mutations.
Mutations are operations that modify data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import strawberry
from django.contrib.auth import get_user_model
from strawberry.types import Info

from .types import ErrorType, SuccessType, UserType

if TYPE_CHECKING:
    from .context import GraphQLContext

User = get_user_model()


@strawberry.input
class UpdateUserInput:
    """Input type for updating user profile."""

    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


@strawberry.type
class UpdateUserPayload:
    """Payload returned from updateUser mutation."""

    user: UserType | None = None
    errors: list[ErrorType] | None = None


@strawberry.type
class Mutation:
    """Root mutation type for GraphQL API.

    All mutations are defined as methods decorated with @strawberry.mutation.
    """

    @strawberry.mutation
    def update_user(
        self,
        info: Info["GraphQLContext", None],
        input: UpdateUserInput,
    ) -> UpdateUserPayload:
        """Update the current user's profile.

        Args:
            input: The fields to update.

        Returns:
            The updated user or errors if validation fails.
        """
        user = info.context.user
        if not user.is_authenticated:
            return UpdateUserPayload(
                errors=[ErrorType(field="auth", message="Authentication required")]
            )

        errors = []

        # Validate username uniqueness if provided
        if input.username is not None:
            if (
                User.objects.exclude(id=user.id)
                .filter(username=input.username)
                .exists()
            ):
                errors.append(
                    ErrorType(field="username", message="Username already taken")
                )

        if errors:
            return UpdateUserPayload(errors=errors)

        # Update fields
        if input.first_name is not None:
            user.first_name = input.first_name
        if input.last_name is not None:
            user.last_name = input.last_name
        if input.username is not None:
            user.username = input.username

        user.save()

        return UpdateUserPayload(
            user=UserType(
                id=user.id,
                email=user.email,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )

    @strawberry.mutation
    def delete_account(
        self,
        info: Info["GraphQLContext", None],
        confirm: bool = False,
    ) -> SuccessType:
        """Delete the current user's account.

        Args:
            confirm: Must be True to confirm deletion.

        Returns:
            Success message or error.
        """
        user = info.context.user
        if not user.is_authenticated:
            return SuccessType(success=False, message="Authentication required")

        if not confirm:
            return SuccessType(
                success=False,
                message="Please confirm deletion by setting confirm=true",
            )

        user.is_active = False
        user.save()

        return SuccessType(success=True, message="Account deactivated successfully")

    # Add more mutations here
    # @strawberry.mutation
    # def create_item(self, info: Info, input: CreateItemInput) -> CreateItemPayload:
    #     ...
'''
        self.create_file(self.app_path / "graphql" / "mutations.py", content)

    def _generate_schema(self) -> None:
        """Generate the main GraphQL schema."""
        content = f'''"""GraphQL schema for {self.app_name}.

This module combines Query and Mutation types into the final schema.
"""

import strawberry

from .mutations import Mutation
from .queries import Query

schema = strawberry.Schema(query=Query, mutation=Mutation)
'''
        self.create_file(self.app_path / "graphql" / "schema.py", content)

    def _generate_graphql_init(self) -> None:
        """Generate the __init__.py for graphql package."""
        content = f'''"""GraphQL package for {self.app_name}.

This package provides GraphQL API functionality using Strawberry.
"""

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
        self.create_file(self.app_path / "graphql" / "__init__.py", content)

    def _generate_jwt_graphql_view(self) -> None:
        """Generate JWT authenticated GraphQL view in core."""
        core_graphql_path = self.project_root / "core" / "graphql.py"

        content = '''"""JWT Authenticated GraphQL View.

This module provides a GraphQL view that integrates with Django Ninja JWT
for authentication. The view parses JWT tokens from the Authorization header
and sets the request.user accordingly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from strawberry.django.views import GraphQLView as BaseGraphQLView

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTAuthenticatedGraphQLView(BaseGraphQLView):
    """GraphQL view with JWT authentication support.

    This view extracts JWT tokens from the Authorization header,
    validates them, and sets the authenticated user on the request.
    If no valid token is provided, the user remains anonymous.

    Usage in urls.py:
        from core.graphql import JWTAuthenticatedGraphQLView
        from myapp.graphql import schema

        urlpatterns = [
            path("graphql/", JWTAuthenticatedGraphQLView.as_view(schema=schema)),
        ]
    """

    def dispatch(
        self, request: "HttpRequest", *args, **kwargs
    ) -> "HttpResponse":
        """Process the request with JWT authentication.

        Extracts and validates JWT token from Authorization header,
        then delegates to the parent GraphQL view.

        Args:
            request: The Django HTTP request.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The HTTP response from the GraphQL view.
        """
        # Set anonymous user as default
        if not hasattr(request, "user") or request.user is None:
            request.user = AnonymousUser()

        # Try to authenticate via JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            user = self._authenticate_token(token)
            if user is not None:
                request.user = user

        return super().dispatch(request, *args, **kwargs)

    def _authenticate_token(self, token: str) -> User | None:
        """Authenticate a JWT token and return the user.

        Args:
            token: The JWT token string.

        Returns:
            The authenticated User or None if authentication fails.
        """
        try:
            from ninja_jwt.tokens import AccessToken

            # Decode and validate the token
            access_token = AccessToken(token)

            # Get user ID from token claims
            user_id = access_token.get("user_id")
            if user_id is None:
                logger.debug("No user_id in token claims")
                return None

            # Fetch the user
            user = User.objects.get(id=user_id)
            if not user.is_active:
                logger.debug("User %s is not active", user_id)
                return None

            return user

        except Exception as e:
            # Token validation failed (expired, invalid, etc.)
            logger.debug("JWT authentication failed: %s", e)
            return None


class AsyncJWTAuthenticatedGraphQLView(JWTAuthenticatedGraphQLView):
    """Async version of JWT authenticated GraphQL view.

    Use this view when running with ASGI for better performance
    with async resolvers.
    """

    pass
'''
        self.create_file(core_graphql_path, content)

    def _update_urls_for_graphql(self) -> None:
        """Update URLs to include GraphQL endpoint."""
        urls_path = self.project_root / "api" / "urls.py"
        if not urls_path.exists():
            self.logger.warning("Main urls.py not found, skipping URL update")
            return

        try:
            content = urls_path.read_text(encoding="utf-8")
            original_content = content

            # Check if GraphQL is already configured
            if (
                "graphql" in content.lower()
                and "JWTAuthenticatedGraphQLView" in content
            ):
                self.logger.info("GraphQL URL already configured")
                return

            # Add imports at the top
            graphql_imports = f"""
# GraphQL imports
from core.graphql import JWTAuthenticatedGraphQLView
from {self.app_name}.graphql import schema as graphql_schema
"""
            # Find a good place to insert imports (after existing imports)
            import_insert_pos = content.find("from todos.controllers")
            if import_insert_pos == -1:
                import_insert_pos = content.find("from core.controllers")

            if import_insert_pos != -1:
                # Find the end of that import line
                line_end = content.find("\n", import_insert_pos)
                content = (
                    content[: line_end + 1] + graphql_imports + content[line_end + 1 :]
                )

            # Add GraphQL URL pattern
            graphql_url = """    # GraphQL endpoint
    path("graphql/", JWTAuthenticatedGraphQLView.as_view(schema=graphql_schema)),
"""
            # Find urlpatterns and insert GraphQL path
            urlpatterns_pos = content.find("urlpatterns = [")
            if urlpatterns_pos != -1:
                # Find the first path entry
                first_path_pos = content.find('path("', urlpatterns_pos)
                if first_path_pos != -1:
                    content = (
                        content[:first_path_pos]
                        + graphql_url
                        + content[first_path_pos:]
                    )

            urls_path.write_text(content, encoding="utf-8")
            self.logger.info("Updated URLs with GraphQL endpoint")

        except Exception as e:
            self.logger.error(f"Failed to update URLs: {e}")
            # Restore original content if there was an error
            try:
                urls_path.write_text(original_content, encoding="utf-8")
            except Exception:
                pass

    def _update_settings_for_graphql(self) -> None:
        """Update Django settings for GraphQL."""
        settings_path = self.project_root / "api" / "settings" / "common.py"
        if not settings_path.exists():
            self.logger.warning("Settings file not found, skipping settings update")
            return

        try:
            content = settings_path.read_text(encoding="utf-8")

            # Check if already configured
            if "STRAWBERRY" in content:
                self.logger.info("Strawberry settings already configured")
                return

            # Add Strawberry configuration
            strawberry_config = """
# =============================================================================
# GraphQL (Strawberry) Configuration
# =============================================================================
STRAWBERRY = {
    # Enable GraphQL playground in development
    "GRAPHIQL": env.bool("GRAPHQL_PLAYGROUND", default=True),
    # Maximum query depth to prevent deeply nested queries
    "MAX_QUERY_DEPTH": 10,
    # Maximum query complexity
    "MAX_QUERY_COMPLEXITY": 100,
}
"""
            content += strawberry_config
            settings_path.write_text(content, encoding="utf-8")
            self.logger.info("Updated settings with Strawberry configuration")

        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")

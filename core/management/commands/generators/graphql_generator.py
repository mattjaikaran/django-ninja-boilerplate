"""GraphQL/Strawberry feature generator.

This generator adds a Strawberry GraphQL API to an existing app: types,
permission classes, a user service that holds every query, queries,
mutations, the schema, one smoke and permission test file, and a
JWT-authenticated GraphQL view in ``core/graphql_view.py``.
"""

import ast

from .base_generator import BaseGenerator
from .templates.graphql_templates import GRAPHQL_VIEW_TEMPLATE, render_graphql_files


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

        for relative_path, content in render_graphql_files(self.app_name).items():
            self.create_file(self.app_path / relative_path, content)
        tests_init = self.app_path / "tests" / "__init__.py"
        if not tests_init.exists():
            self.create_file(tests_init, "")

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
        print("3. Visit /api/graphql/ to access the GraphQL playground")

    def _generate_jwt_graphql_view(self) -> None:
        """Generate the JWT authenticated GraphQL view in core.

        The view lives in ``core/graphql_view.py``, not ``core/graphql.py``:
        with ``--app-name=core`` the generator also creates a ``core/graphql/``
        package, and a package shadows a module of the same name.
        """
        self.create_file(
            self.project_root / "core" / "graphql_view.py",
            GRAPHQL_VIEW_TEMPLATE.replace("__APP__", self.app_name),
        )

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

            # Add the imports; ruff moves them into isort position below.
            graphql_imports = (
                "from core.graphql_view import JWTAuthenticatedGraphQLView\n"
                f"from {self.app_name}.graphql import schema as graphql_schema\n"
            )
            # Insert after the last top-level import statement. Searching for
            # one import line split multi-line parenthesized imports.
            lines = content.splitlines(keepends=True)
            import_ends = [
                node.end_lineno
                for node in ast.parse(content).body
                if isinstance(node, ast.Import | ast.ImportFrom)
            ]
            if import_ends:
                insert_at = max(n for n in import_ends if n is not None)
                content = (
                    "".join(lines[:insert_at])
                    + graphql_imports
                    + "".join(lines[insert_at:])
                )

            # Add GraphQL URL pattern
            # Under /api/ so ApiCsrfMiddleware applies the API CSRF rule and
            # the bundled nginx, which proxies only /api/ and /admin/, serves it.
            graphql_url = """    # GraphQL endpoint
    path("api/graphql/", JWTAuthenticatedGraphQLView.as_view(schema=graphql_schema)),
"""
            # Find urlpatterns and insert GraphQL path
            urlpatterns_pos = content.find("urlpatterns = [")
            if urlpatterns_pos != -1:
                # Find the first path entry
                first_path_pos = content.find('path("', urlpatterns_pos)
                if first_path_pos != -1:
                    # Insert a whole line so the existing entry keeps its indent.
                    line_start = content.rfind("\n", 0, first_path_pos) + 1
                    content = content[:line_start] + graphql_url + content[line_start:]

            urls_path.write_text(content, encoding="utf-8")
            self.run_ruff("check", "--fix", "--select", "I", urls_path)
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
    # Serve the GraphiQL IDE at /api/graphql/ (read by JWTAuthenticatedGraphQLView)
    "GRAPHIQL": env.bool("GRAPHQL_PLAYGROUND", default=True),
    # Deepest query the schema accepts (QueryDepthLimiter in schema.py)
    "MAX_QUERY_DEPTH": 10,
}
"""
            content += strawberry_config
            settings_path.write_text(content, encoding="utf-8")
            self.logger.info("Updated settings with Strawberry configuration")

        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")

"""Regression tests for the GraphQL feature generator's output paths."""

import ast

import pytest

from core.management.commands.generators.graphql_generator import GraphQLGenerator

URLS = '''"""URL configuration."""

from django.urls import path

from todos.controllers import (
    TodoController,
    TodoControllerBasic,
)

urlpatterns = [
    path("admin/", admin.site.urls),
]
'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "api" / "settings").mkdir(parents=True)
    (tmp_path / "api" / "urls.py").write_text(URLS)
    (tmp_path / "api" / "settings" / "common.py").write_text("")
    (tmp_path / "core").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_core_app_gets_a_view_module_the_package_cannot_shadow(project):
    GraphQLGenerator("core").generate()

    assert (project / "core" / "graphql" / "__init__.py").is_file()
    assert (project / "core" / "graphql_view.py").is_file()
    # A core/graphql.py module would be shadowed by the core/graphql/ package.
    assert not (project / "core" / "graphql.py").exists()


def test_urls_edit_keeps_imports_and_patterns_whole(project):
    GraphQLGenerator("core").generate()

    text = (project / "api" / "urls.py").read_text()
    tree = ast.parse(text)
    modules = sorted(n.module for n in tree.body if isinstance(n, ast.ImportFrom))
    assert modules == [
        "core.graphql",
        "core.graphql_view",
        "django.urls",
        "todos.controllers",
    ]
    # The existing entry keeps its indent after the GraphQL path is inserted.
    assert '\n    path("admin/", admin.site.urls),\n' in text

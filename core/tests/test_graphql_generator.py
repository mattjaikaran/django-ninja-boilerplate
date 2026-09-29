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


@pytest.mark.unit
def test_core_app_gets_a_view_module_the_package_cannot_shadow(project):
    GraphQLGenerator("core").generate()

    assert (project / "core" / "graphql" / "__init__.py").is_file()
    assert (project / "core" / "graphql_view.py").is_file()
    # A core/graphql.py module would be shadowed by the core/graphql/ package.
    assert not (project / "core" / "graphql.py").exists()


@pytest.mark.unit
def test_urls_imports_land_after_a_multiline_import(project):
    GraphQLGenerator("core").generate()

    tree = ast.parse((project / "api" / "urls.py").read_text())
    modules = [n.module for n in tree.body if isinstance(n, ast.ImportFrom)]
    assert modules[-2:] == ["core.graphql_view", "core.graphql"]

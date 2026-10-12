"""Base generator class for all feature generators."""

from __future__ import annotations

import ast
import keyword
import logging
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .codegen import PACKAGE_INIT, ResourceNames, from_import

logger = logging.getLogger(__name__)


class GeneratorError(Exception):
    """Custom exception for generator errors."""


class BaseGenerator(ABC):
    """Base class for all feature generators."""

    def __init__(self, app_name: str, minimal: bool = False):
        """Initialize the generator.

        Args:
            app_name: Name of the Django app to create
            minimal: Whether to generate minimal version
        """
        self.app_name = app_name
        self.minimal = minimal
        self.project_root = Path.cwd()
        self.app_path = self.project_root / app_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # True once create_django_app() has run startapp_extended in this run.
        self.created_app = False

        # Validation
        self._validate_app_name()

    def _validate_app_name(self) -> None:
        """Validate the app name."""
        if not self.app_name:
            msg = "App name cannot be empty"
            raise GeneratorError(msg)

        if not self.app_name.isidentifier():
            msg = f"App name '{self.app_name}' is not a valid Python identifier"
            raise GeneratorError(msg)

        # Check for reserved Python keywords
        if keyword.iskeyword(self.app_name):
            msg = f"App name '{self.app_name}' is a reserved Python keyword"
            raise GeneratorError(msg)

    def create_django_app(self) -> None:
        """Create the Django app using startapp_extended command."""
        if self.app_path.exists():
            self.logger.info(
                "App '%s' already exists, skipping creation...", self.app_name
            )
            return

        try:
            subprocess.run(
                [sys.executable, "manage.py", "startapp_extended", self.app_name],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info("Successfully created Django app: %s", self.app_name)
            self.created_app = True
        except subprocess.CalledProcessError as e:
            self.logger.exception("Failed to create Django app: %s", e.stderr)
            msg = f"Failed to create Django app: {e.stderr}"
            raise GeneratorError(msg) from e

    def remove_scaffold(self) -> None:
        """Remove the startapp_extended CRUD scaffold so a feature can replace it.

        Call it right after create_django_app(). It deletes the scaffold's
        model, schema, service, controller, admin, test, data command and
        README, and empties the package ``__init__.py`` files that export
        them. The feature generator then writes its own files and exports.
        It does nothing when the app existed before this run.
        """
        if not self.created_app:
            return
        names = ResourceNames.from_app_name(self.app_name)
        snake = names.model_snake
        scaffold = (
            f"models/{snake}.py",
            f"schemas/{snake}_schema.py",
            f"services/{snake}_service.py",
            f"controllers/{snake}_controller.py",
            f"admin/{snake}_admin.py",
            f"tests/test_{snake}.py",
            f"management/commands/generate_{self.app_name}_data.py",
            "README.md",
        )
        for relative_path in scaffold:
            (self.app_path / relative_path).unlink(missing_ok=True)
        for package in ("models", "schemas", "services", "controllers", "admin"):
            self.create_file(self.app_path / package / "__init__.py", PACKAGE_INIT)

    def create_file(
        self, file_path: Path, content: str, overwrite: bool = True
    ) -> None:
        """Create a file with the given content.

        Args:
            file_path: Path to the file to create
            content: Content to write to the file
            overwrite: Whether to overwrite existing files
        """
        if file_path.exists() and not overwrite:
            self.logger.warning(f"File already exists, skipping: {file_path}")
            return

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            self.logger.info(f"Created: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to create file {file_path}: {e}")
            raise GeneratorError(f"Failed to create file {file_path}: {e}")

    def update_pyproject_toml(self, dependencies: list[str]) -> None:
        """Update pyproject.toml with new dependencies.

        Args:
            dependencies: List of dependencies to add
        """
        if not dependencies:
            return

        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            self.logger.warning("pyproject.toml not found, skipping dependency update")
            return

        try:
            content = pyproject_path.read_text(encoding="utf-8")
            original_content = content

            # Add dependencies that aren't already present
            new_deps = []
            for dep in dependencies:
                if dep not in content:
                    new_deps.append(dep)

            if not new_deps:
                self.logger.info("All dependencies already present in pyproject.toml")
                return

            # Find the dependencies section and add new dependencies
            lines = content.split("\n")
            dependencies_section_found = False

            for i, line in enumerate(lines):
                # Look for dependencies section
                if "[tool.hatch.envs.default]" in line or "dependencies = [" in line:
                    dependencies_section_found = True
                elif (
                    dependencies_section_found
                    and line.strip().startswith('"')
                    and line.strip().endswith('",')
                ):
                    # Insert new dependencies before the last dependency
                    for dep in reversed(new_deps):  # Reverse to maintain order
                        lines.insert(i + 1, f'    "{dep}",')
                    break

            if dependencies_section_found:
                content = "\n".join(lines)
                pyproject_path.write_text(content, encoding="utf-8")
                self.logger.info(
                    f"Updated pyproject.toml with dependencies: {', '.join(new_deps)}"
                )
            else:
                self.logger.warning(
                    "Could not find dependencies section in pyproject.toml"
                )

        except Exception as e:
            self.logger.error(f"Failed to update pyproject.toml: {e}")
            # Restore original content if there was an error
            try:
                pyproject_path.write_text(original_content, encoding="utf-8")
            except Exception:
                pass

    def update_settings(self, app_name: str, settings_updates: dict[str, Any]) -> None:
        """Update Django settings with new configurations.

        Args:
            app_name: Name of the app to add to INSTALLED_APPS
            settings_updates: Dictionary of settings to update
        """
        settings_path = self.project_root / "api" / "settings" / "common.py"
        if not settings_path.exists():
            self.logger.warning("Settings file not found, skipping settings update")
            return

        try:
            content = settings_path.read_text(encoding="utf-8")
            original_content = content
            modified = False

            # Add app to INSTALLED_APPS if not already there
            installed = re.search(
                rf"^\s*[\"']{re.escape(app_name)}[\"']\s*,", content, re.MULTILINE
            )
            if not installed and "INSTALLED_APPS" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "INSTALLED_APPS" in line and "=" in line:
                        # Find the closing bracket and insert before it
                        j = i + 1
                        bracket_depth = 0
                        found_closing = False

                        while j < len(lines):
                            if "[" in lines[j]:
                                bracket_depth += lines[j].count("[")
                            if "]" in lines[j]:
                                bracket_depth -= lines[j].count("]")
                                if bracket_depth <= 0:
                                    lines.insert(j, f'    "{app_name}",')
                                    found_closing = True
                                    modified = True
                                    break
                            j += 1

                        if found_closing:
                            break

                if modified:
                    content = "\n".join(lines)

            # Add other settings as one block per call
            missing = {
                key: value
                for key, value in settings_updates.items()
                if key not in content
            }
            if missing:
                block = "".join(
                    f"{key} = {value!r}\n" for key, value in missing.items()
                )
                content = (
                    f"{content.rstrip()}\n\n\n# {app_name.title()} settings\n{block}"
                )
                modified = True

            if modified:
                settings_path.write_text(content, encoding="utf-8")
                # Keep the file ruff-clean: sorted imports, formatted values.
                self.run_ruff("check", "--fix", "--select", "I", settings_path)
                self.run_ruff("format", settings_path)
                self.logger.info(f"Updated settings with {app_name} configuration")
            else:
                self.logger.info(f"No settings updates needed for {app_name}")

        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")
            # Restore original content if there was an error
            try:
                settings_path.write_text(original_content, encoding="utf-8")
            except Exception:
                pass

    def create_migration(self) -> None:
        """Create, format and apply the app's migrations.

        A failed makemigrations or ruff run raises GeneratorError. A failed
        migrate only logs a warning: the database may not be running.
        """
        try:
            subprocess.run(
                [sys.executable, "manage.py", "makemigrations", self.app_name],
                check=True,
                capture_output=True,
                text=True,
            )
            # makemigrations output is not isort-sorted or ruff-formatted.
            migrations_dir = self.app_path / "migrations"
            self.run_ruff("check", "--fix", "--select", "I", migrations_dir)
            self.run_ruff("format", migrations_dir)
        except subprocess.CalledProcessError as e:
            msg = f"Failed to create migrations for {self.app_name}: {e.stderr}"
            raise GeneratorError(msg) from e
        self.logger.info("Created migrations for %s", self.app_name)

        try:
            subprocess.run(
                [sys.executable, "manage.py", "migrate"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            self.logger.warning("Migrate failed for %s: %s", self.app_name, e.stderr)
            return
        self.logger.info("Applied migrations for %s", self.app_name)

    def update_urls(self, app_name: str, *controller_classes: str) -> None:
        """Import and register the app's controllers in ``api/urls.py``.

        The import goes after the last top-level import and the registration
        after the last top-level ``api.register_controllers(...)`` call, so
        neither lands inside a multi-line statement; ``ruff --select I`` then
        sorts the import into place. A second call with the same controllers
        changes nothing.

        Args:
            app_name: Name of the app
            controller_classes: Controllers to register. Defaults to the
                controller ``startapp_extended`` generates for the app.
        """
        urls_path = self.project_root / "api" / "urls.py"
        if not urls_path.exists():
            self.logger.warning("Main urls.py not found, skipping URL update")
            return

        classes = controller_classes or (
            f"{ResourceNames.from_app_name(app_name).model_name}Controller",
        )
        module = f"{app_name}.controllers"
        content = urls_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        registers = [
            node
            for node in tree.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "api.register_controllers"
        ]
        if not registers:
            msg = f"No top-level api.register_controllers(...) call in {urls_path}"
            raise GeneratorError(msg)
        register = registers[0]

        imports = [
            node
            for node in tree.body
            if isinstance(node, ast.Import | ast.ImportFrom)
            and node.lineno < register.lineno
        ]
        existing_import = next(
            (
                node
                for node in imports
                if isinstance(node, ast.ImportFrom) and node.module == module
            ),
            None,
        )
        imported = (
            {alias.name for alias in existing_import.names}
            if existing_import
            else set()
        )
        registered = {
            arg.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "api.register_controllers"
            for arg in node.args
            if isinstance(arg, ast.Name)
        }
        to_import = [name for name in classes if name not in imported]
        to_register = [name for name in classes if name not in registered]
        if not to_import and not to_register:
            self.logger.info("URL configuration already up to date for %s", app_name)
            return

        lines = content.split("\n")
        # Edit bottom-up so the earlier line numbers stay valid.
        if to_register:
            call = f"api.register_controllers({', '.join(to_register)})"
            if len(call) > 88:
                body = "".join(f"    {name},\n" for name in to_register)
                call = f"api.register_controllers(\n{body})"
            lines.insert(registers[-1].end_lineno, call)
        if to_import:
            if existing_import:
                statement = from_import(module, *sorted(imported), *to_import)
                start, end = existing_import.lineno, existing_import.end_lineno
                lines[start - 1 : end] = [statement]
            else:
                lines.insert(imports[-1].end_lineno, from_import(module, *to_import))

        urls_path.write_text("\n".join(lines), encoding="utf-8")
        # Move the new import into isort position within its section.
        self.run_ruff("check", "--fix", "--select", "I", urls_path)
        self.logger.info("Registered %s in %s", ", ".join(classes), urls_path)

    @staticmethod
    def run_ruff(*args: str | Path) -> None:
        """Run ruff from this interpreter's environment. Raise on failure."""
        subprocess.run(
            [sys.executable, "-m", "ruff", *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
        )

    # Template helper methods
    def get_template_context(self) -> dict[str, Any]:
        """Get common template context variables."""
        return {
            "app_name": self.app_name,
            "app_name_title": self.app_name.title(),
            "minimal": self.minimal,
        }

    def render_template(self, template_content: str, **extra_context) -> str:
        """Render a template with context variables."""
        context = self.get_template_context()
        context.update(extra_context)
        return template_content.format(**context)

    # File generation helpers
    def create_init_file(
        self, directory: Path, imports: list[str], all_exports: list[str]
    ) -> None:
        """Create an __init__.py file with imports and __all__."""
        content = ""
        if imports:
            content += "\n".join(imports) + "\n\n"
        if all_exports:
            all_list = ", ".join(f'"{export}"' for export in all_exports)
            content += f"__all__ = [{all_list}]\n"

        self.create_file(directory / "__init__.py", content)

    def create_directory_structure(self, directories: list[str]) -> None:
        """Create multiple directories under the app path."""
        for directory in directories:
            dir_path = self.app_path / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {dir_path}")

    @abstractmethod
    def generate(self) -> None:
        """Generate the feature. Must be implemented by subclasses."""

    def run_generation(self) -> None:
        """Run the complete generation process with error handling."""
        try:
            self.logger.info(f"Starting generation of {self.app_name} feature...")
            self.generate()
            self.logger.info(f"Successfully generated {self.app_name} feature!")
        except GeneratorError as e:
            self.logger.error(f"Generation failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during generation: {e}")
            raise GeneratorError(f"Unexpected error: {e}") from e

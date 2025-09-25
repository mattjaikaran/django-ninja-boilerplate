"""Base generator class for all feature generators."""

import keyword
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

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
                ["python", "manage.py", "startapp_extended", self.app_name],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info("Successfully created Django app: %s", self.app_name)
        except subprocess.CalledProcessError as e:
            self.logger.exception("Failed to create Django app: %s", e.stderr)
            msg = f"Failed to create Django app: {e.stderr}"
            raise GeneratorError(msg) from e

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

    def update_pyproject_toml(self, dependencies: List[str]) -> None:
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
            except:
                pass

    def update_settings(self, app_name: str, settings_updates: Dict[str, Any]) -> None:
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
            if app_name not in content and "INSTALLED_APPS" in content:
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

            # Add other settings
            for key, value in settings_updates.items():
                if key not in content:
                    content += f"\n\n# {app_name.title()} settings\n{key} = {value!r}\n"
                    modified = True

            if modified:
                settings_path.write_text(content, encoding="utf-8")
                self.logger.info(f"Updated settings with {app_name} configuration")
            else:
                self.logger.info(f"No settings updates needed for {app_name}")

        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")
            # Restore original content if there was an error
            try:
                settings_path.write_text(original_content, encoding="utf-8")
            except:
                pass

    def create_migration(self) -> None:
        """Create and run migrations for the new app."""
        try:
            # Create migrations
            result = subprocess.run(
                ["python", "manage.py", "makemigrations", self.app_name],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info(f"Created migrations for {self.app_name}")

            # Apply migrations
            result = subprocess.run(
                ["python", "manage.py", "migrate"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info(f"Applied migrations for {self.app_name}")

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Migration failed: {e.stderr}")
            # Don't raise error for migrations as they might fail for valid reasons

    def update_urls(self, app_name: str) -> None:
        """Update main urls.py to include the new app's URLs.

        Args:
            app_name: Name of the app
        """
        urls_path = self.project_root / "api" / "urls.py"
        if not urls_path.exists():
            self.logger.warning("Main urls.py not found, skipping URL update")
            return

        try:
            content = urls_path.read_text(encoding="utf-8")
            original_content = content
            modified = False

            # Generate controller class name (capitalized + Controller)
            controller_class = f"{app_name.title()}Controller"
            controller_import = f"from {app_name}.controllers import {controller_class}"
            controller_register = f"api.register_controllers({controller_class})"

            # Add controller import if not present
            if controller_import not in content:
                lines = content.split("\n")
                import_added = False

                # Find where to insert the import
                for i, line in enumerate(lines):
                    if line.strip().startswith("from") and "controllers" in line:
                        lines.insert(i + 1, controller_import)
                        import_added = True
                        modified = True
                        break

                # If no controller imports found, add after other imports
                if not import_added:
                    for i, line in enumerate(lines):
                        if line.strip().startswith("from") or line.strip().startswith(
                            "import"
                        ):
                            continue
                        lines.insert(i, controller_import)
                        modified = True
                        break

                content = "\n".join(lines)

            # Add controller registration if not present
            if controller_register not in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "api.register_controllers" in line:
                        lines.insert(i + 1, controller_register)
                        modified = True
                        break
                content = "\n".join(lines)

            if modified:
                urls_path.write_text(content, encoding="utf-8")
                self.logger.info(f"Updated URLs with {app_name} controller")
            else:
                self.logger.info(f"URL configuration already up to date for {app_name}")

        except Exception as e:
            self.logger.error(f"Failed to update URLs: {e}")
            # Restore original content if there was an error
            try:
                urls_path.write_text(original_content, encoding="utf-8")
            except:
                pass

    # Template helper methods
    def get_template_context(self) -> Dict[str, Any]:
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
        self, directory: Path, imports: List[str], all_exports: List[str]
    ) -> None:
        """Create an __init__.py file with imports and __all__."""
        content = ""
        if imports:
            content += "\n".join(imports) + "\n\n"
        if all_exports:
            all_list = ", ".join(f'"{export}"' for export in all_exports)
            content += f"__all__ = [{all_list}]\n"

        self.create_file(directory / "__init__.py", content)

    def create_directory_structure(self, directories: List[str]) -> None:
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

"""Base generator with common functionality."""

import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from django_ninja_matt.config import ProjectConfig, TemplateContext
from django_ninja_matt.utils.console import (
    print_error,
    print_info,
    print_success,
)
from django_ninja_matt.utils.git import (
    create_initial_commit,
    git_available,
    init_repo,
    remove_git_history,
)


class BaseGenerator:
    """Base class for project generators."""

    def __init__(self, config: ProjectConfig) -> None:
        """Initialize generator with project config."""
        self.config = config
        self.context = TemplateContext(config)
        self.template_dir = Path(__file__).parent / "templates"

    def create_directory(self) -> bool:
        """Create the project directory."""
        try:
            self.config.path.mkdir(parents=True, exist_ok=False)
            print_success(f"Created directory: {self.config.path}")
            return True
        except FileExistsError:
            print_error(f"Directory already exists: {self.config.path}")
            return False

    def copy_template_dir(self, src: Path, dest: Path) -> None:
        """Copy a template directory with Jinja2 rendering.

        Args:
            src: Source template directory
            dest: Destination directory
        """
        if not src.exists():
            print_info(f"Template directory not found: {src}")
            return

        env = Environment(
            loader=FileSystemLoader(str(src)),
            keep_trailing_newline=True,
        )
        context = self.context.to_dict()

        for item in src.rglob("*"):
            if item.is_file():
                # Calculate relative path
                rel_path = item.relative_to(src)

                # Process filename (replace template vars)
                dest_path = dest / self._process_path(str(rel_path), context)
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Check if file should be rendered as template
                if item.suffix in {
                    ".py",
                    ".txt",
                    ".md",
                    ".yml",
                    ".yaml",
                    ".json",
                    ".toml",
                    ".sh",
                    ".env",
                }:
                    try:
                        template = env.get_template(str(rel_path))
                        content = template.render(**context)
                        dest_path.write_text(content)
                    except Exception:
                        # If template rendering fails, copy as-is
                        shutil.copy2(item, dest_path)
                else:
                    # Copy binary files as-is
                    shutil.copy2(item, dest_path)

    def _process_path(self, path: str, context: dict) -> str:
        """Process path, replacing template variables.

        Args:
            path: Path string with potential template vars
            context: Template context

        Returns:
            Processed path string
        """
        # Replace __project_name__ with actual project name
        path = path.replace("__project_name__", context["project_name"])
        path = path.replace("__python_package_name__", context["python_package_name"])
        return path

    def update_file_content(
        self,
        file_path: Path,
        replacements: dict[str, str],
    ) -> None:
        """Update file content with string replacements.

        Args:
            file_path: Path to the file
            replacements: Dict of old -> new string replacements
        """
        if not file_path.exists():
            return

        content = file_path.read_text()
        for old, new in replacements.items():
            content = content.replace(old, new)
        file_path.write_text(content)

    def update_file_regex(
        self,
        file_path: Path,
        pattern: str,
        replacement: str,
    ) -> None:
        """Update file content with regex replacement.

        Args:
            file_path: Path to the file
            pattern: Regex pattern
            replacement: Replacement string
        """
        if not file_path.exists():
            return

        content = file_path.read_text()
        content = re.sub(pattern, replacement, content)
        file_path.write_text(content)

    def init_git_repository(self) -> None:
        """Initialize git repository if requested."""
        if not self.config.init_git:
            return

        if not git_available():
            print_info("Git not available, skipping repository initialization")
            return

        # Remove existing .git if cloned from template
        remove_git_history(self.config.path)

        # Initialize new repository
        init_repo(self.config.path)

        # Create initial commit
        create_initial_commit(
            self.config.path,
            f"Initial commit: {self.config.display_name}",
        )

    def cleanup_template_files(self) -> None:
        """Remove template-specific files that shouldn't be in final project."""
        files_to_remove = [
            ".git",
            "cli",  # CLI source (if copied)
        ]

        for filename in files_to_remove:
            file_path = self.config.path / filename
            if file_path.exists():
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

    def run(self) -> bool:
        """Run the generator. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement run()")

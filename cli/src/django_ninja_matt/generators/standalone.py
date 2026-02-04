"""Standalone API project generator."""

from django_ninja_matt.config import DEFAULT_BRANCH, REPO_URLS, ProjectConfig
from django_ninja_matt.generators.base import BaseGenerator
from django_ninja_matt.utils.console import (
    create_progress,
    print_error,
    print_info,
)
from django_ninja_matt.utils.git import clone_repo, git_available


class StandaloneGenerator(BaseGenerator):
    """Generator for standalone Django API projects."""

    def run(self) -> bool:
        """Generate a standalone API project."""
        with create_progress() as progress:
            task = progress.add_task("Creating project...", total=5)

            # Step 1: Clone repository
            progress.update(task, description="Cloning template...")
            if not self._clone_template():
                return False
            progress.advance(task)

            # Step 2: Customize project
            progress.update(task, description="Customizing project...")
            self._customize_project()
            progress.advance(task)

            # Step 3: Update configuration
            progress.update(task, description="Updating configuration...")
            self._update_configuration()
            progress.advance(task)

            # Step 4: Clean up
            progress.update(task, description="Cleaning up...")
            self.cleanup_template_files()
            progress.advance(task)

            # Step 5: Initialize git
            progress.update(task, description="Initializing git...")
            self.init_git_repository()
            progress.advance(task)

        return True

    def _clone_template(self) -> bool:
        """Clone the Django Ninja boilerplate repository."""
        if not git_available():
            print_error("Git is required to create projects")
            return False

        return clone_repo(
            url=REPO_URLS["backend"],
            destination=self.config.path,
            branch=DEFAULT_BRANCH,
        )

    def _customize_project(self) -> None:
        """Customize the project with user's settings."""
        # Update pyproject.toml
        pyproject = self.config.path / "pyproject.toml"
        if pyproject.exists():
            self.update_file_regex(
                pyproject,
                r'name = "django-ninja-boilerplate"',
                f'name = "{self.config.name}"',
            )
            self.update_file_regex(
                pyproject,
                r'description = ".*"',
                f'description = "{self.config.description or self.config.display_name} API"',
            )

        # Update VERSION file
        version_file = self.config.path / "VERSION"
        if version_file.exists():
            version_file.write_text("0.1.0\n")

        # Update README
        readme = self.config.path / "README.md"
        if readme.exists():
            content = f"""# {self.config.display_name}

{self.config.description or "A Django Ninja API project."}

## Quick Start

```bash
# Bootstrap the development environment
make setup

# Or step by step:
make doctor    # Validate environment
make build     # Build Docker images
make up        # Start services
make migrate   # Run migrations
```

## Available Commands

```bash
make help      # Show all commands
make up        # Start services
make down      # Stop services
make logs      # View logs
make test      # Run tests
make doctor    # Check environment
```

## API Documentation

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- Health Check: http://localhost:8000/api/health/

## Project Structure

```
{self.config.name}/
├── api/              # Django project settings
├── core/             # Core app (users, auth)
├── todos/            # Example app
├── docker/           # Docker configurations
├── scripts/          # Setup and utility scripts
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

Created with [Django Ninja Boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate)
"""
            readme.write_text(content)

    def _update_configuration(self) -> None:
        """Update project configuration based on options."""
        # If not using Celery, remove Celery services from docker-compose
        if not self.config.use_celery:
            self._remove_celery_config()

        # If not using Redis (and not using Celery), remove Redis
        if not self.config.use_redis and not self.config.use_celery:
            self._remove_redis_config()

    def _remove_celery_config(self) -> None:
        """Remove Celery configuration from the project."""
        # Remove Celery from pyproject.toml dependencies
        pyproject = self.config.path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Remove celery-related dependencies
            lines = content.split("\n")
            filtered_lines = [
                line
                for line in lines
                if not any(pkg in line.lower() for pkg in ["celery", "flower"])
            ]
            pyproject.write_text("\n".join(filtered_lines))

        print_info("Removed Celery configuration")

    def _remove_redis_config(self) -> None:
        """Remove Redis configuration from the project."""
        print_info("Note: Redis configuration kept for caching support")


def generate_standalone(config: ProjectConfig) -> bool:
    """Generate a standalone API project.

    Args:
        config: Project configuration

    Returns:
        True if successful
    """
    generator = StandaloneGenerator(config)
    return generator.run()

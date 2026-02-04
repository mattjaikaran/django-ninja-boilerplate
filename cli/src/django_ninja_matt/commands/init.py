"""Init command - create a new project."""

from pathlib import Path

import questionary
from rich.panel import Panel
from rich.text import Text

from django_ninja_matt.config import (
    DeploymentTarget,
    ProjectConfig,
    ProjectType,
)
from django_ninja_matt.generators.monorepo import generate_monorepo
from django_ninja_matt.generators.standalone import generate_standalone
from django_ninja_matt.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
)


def show_welcome() -> None:
    """Show welcome banner."""
    text = Text()
    text.append("Django Ninja Boilerplate", style="bold cyan")
    text.append("\n")
    text.append("Modern Django API scaffolding with best practices", style="dim")

    panel = Panel(
        text,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def prompt_project_type() -> ProjectType:
    """Prompt user for project type."""
    choices = [
        questionary.Choice(
            title="Standalone API - Django Ninja backend only",
            value=ProjectType.STANDALONE,
        ),
        questionary.Choice(
            title="Fullstack Monorepo - Django backend + React frontend",
            value=ProjectType.MONOREPO,
        ),
    ]

    result = questionary.select(
        "What type of project would you like to create?",
        choices=choices,
        style=questionary.Style(
            [
                ("highlighted", "fg:cyan bold"),
                ("selected", "fg:green"),
            ]
        ),
    ).ask()

    if result is None:
        raise KeyboardInterrupt()
    return result


def prompt_features(project_type: ProjectType) -> dict:
    """Prompt user for feature selection."""
    features = {}

    # Celery
    features["use_celery"] = questionary.confirm(
        "Include Celery for background tasks?",
        default=True,
    ).ask()

    if features["use_celery"] is None:
        raise KeyboardInterrupt()

    # Redis (required for Celery, optional otherwise)
    if features["use_celery"]:
        features["use_redis"] = True
        print_info("Redis will be included (required for Celery)")
    else:
        features["use_redis"] = questionary.confirm(
            "Include Redis for caching?",
            default=True,
        ).ask()
        if features["use_redis"] is None:
            raise KeyboardInterrupt()

    return features


def prompt_deployment() -> DeploymentTarget:
    """Prompt user for deployment target."""
    choices = [
        questionary.Choice(
            title="Docker Compose - Local/self-hosted deployment",
            value=DeploymentTarget.DOCKER,
        ),
        questionary.Choice(
            title="Railway - PaaS deployment with Railway",
            value=DeploymentTarget.RAILWAY,
        ),
        questionary.Choice(
            title="Render - PaaS deployment with Render",
            value=DeploymentTarget.RENDER,
        ),
        questionary.Choice(
            title="Kubernetes - Container orchestration with Helm",
            value=DeploymentTarget.KUBERNETES,
        ),
    ]

    result = questionary.select(
        "What's your primary deployment target?",
        choices=choices,
        style=questionary.Style(
            [
                ("highlighted", "fg:cyan bold"),
                ("selected", "fg:green"),
            ]
        ),
    ).ask()

    if result is None:
        raise KeyboardInterrupt()
    return result


def prompt_confirmation(config: ProjectConfig) -> bool:
    """Show summary and confirm project creation."""
    console.print()
    console.print("[bold]Project Summary[/bold]")
    console.print("-" * 40)
    console.print(f"  Name: [cyan]{config.name}[/cyan]")
    console.print(f"  Path: [cyan]{config.path}[/cyan]")
    console.print(f"  Type: [cyan]{config.project_type.value}[/cyan]")
    console.print(f"  Celery: [cyan]{'Yes' if config.use_celery else 'No'}[/cyan]")
    console.print(f"  Redis: [cyan]{'Yes' if config.use_redis else 'No'}[/cyan]")
    console.print(f"  Deployment: [cyan]{config.deployment_target.value}[/cyan]")
    console.print(f"  Git init: [cyan]{'Yes' if config.init_git else 'No'}[/cyan]")
    console.print()

    result = questionary.confirm(
        "Create project with these settings?",
        default=True,
    ).ask()

    return result if result is not None else False


def run_init(
    name: str,
    path: Path,
    project_type: ProjectType | None = None,
    deployment: DeploymentTarget | None = None,
    use_celery: bool = True,
    use_redis: bool = True,
    init_git: bool = True,
    skip_prompts: bool = False,
) -> None:
    """Run the init command to create a new project.

    Args:
        name: Project name
        path: Parent directory for the project
        project_type: Project type (standalone/monorepo)
        deployment: Deployment target
        use_celery: Include Celery
        use_redis: Include Redis
        init_git: Initialize git repository
        skip_prompts: Skip confirmation prompts
    """
    show_welcome()

    # Validate project path
    project_path = path / name
    if project_path.exists():
        print_error(f"Directory already exists: {project_path}")
        raise SystemExit(1)

    try:
        # Interactive prompts if needed
        if project_type is None:
            project_type = prompt_project_type()

        if deployment is None and not skip_prompts:
            deployment = prompt_deployment()
        elif deployment is None:
            deployment = DeploymentTarget.DOCKER

        if not skip_prompts:
            features = prompt_features(project_type)
            use_celery = features["use_celery"]
            use_redis = features["use_redis"]

        # Create config
        config = ProjectConfig(
            name=name,
            path=project_path,
            project_type=project_type,
            deployment_target=deployment,
            use_celery=use_celery,
            use_redis=use_redis,
            init_git=init_git,
        )

        # Confirm
        if not skip_prompts:
            if not prompt_confirmation(config):
                print_info("Project creation cancelled")
                return

        # Generate project
        console.print()
        print_header(f"Creating {config.display_name}")

        if config.is_monorepo:
            generate_monorepo(config)
        else:
            generate_standalone(config)

        # Success message
        console.print()
        print_success(f"Project created at {project_path}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  cd {name}")
        console.print("  make setup")
        console.print()

    except KeyboardInterrupt:
        console.print()
        print_info("Project creation cancelled")
        raise SystemExit(130)

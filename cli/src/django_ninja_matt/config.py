"""Configuration dataclasses for project scaffolding."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ProjectType(str, Enum):
    """Project type options."""

    STANDALONE = "standalone"
    MONOREPO = "monorepo"


class FrontendFramework(str, Enum):
    """Frontend framework options for monorepo projects."""

    REACT_VITE = "react-vite"
    # Future: NEXTJS = "nextjs"
    # Future: VUE_VITE = "vue-vite"


class DeploymentTarget(str, Enum):
    """Deployment target options."""

    DOCKER = "docker"
    RAILWAY = "railway"
    RENDER = "render"
    KUBERNETES = "kubernetes"


class AuthMethod(str, Enum):
    """Authentication method options."""

    JWT = "jwt"
    SESSION = "session"
    OAUTH = "oauth"
    OTP = "otp"


class EmailBackend(str, Enum):
    """Email backend options for the generated project.

    Attributes:
        CONSOLE: Logs emails to the console (default, for local development).
        RESEND: Sends emails via the Resend API using django-anymail.
        SMTP: Sends emails via a standard SMTP server.
    """

    CONSOLE = "console"
    RESEND = "resend"
    SMTP = "smtp"


@dataclass
class ProjectConfig:
    """Configuration for a new project."""

    # Basic info
    name: str
    path: Path
    description: str = ""

    # Project type
    project_type: ProjectType = ProjectType.STANDALONE
    frontend_framework: FrontendFramework | None = None

    # Features
    use_celery: bool = True
    use_redis: bool = True
    use_docker: bool = True
    auth_methods: list[AuthMethod] = field(default_factory=lambda: [AuthMethod.JWT])

    # Code generation options
    include_docstrings: bool = False
    email_backend: EmailBackend = EmailBackend.CONSOLE

    # Deployment
    deployment_target: DeploymentTarget = DeploymentTarget.DOCKER
    single_container: bool = False

    # Git
    init_git: bool = True
    git_remote: str = ""

    # Author info
    author_name: str = ""
    author_email: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize configuration."""
        # Ensure path is a Path object
        if isinstance(self.path, str):
            self.path = Path(self.path)

        # Normalize project name (lowercase, hyphens)
        self.name = self.name.lower().replace("_", "-").replace(" ", "-")

        # Set frontend framework for monorepo
        if self.project_type == ProjectType.MONOREPO and not self.frontend_framework:
            self.frontend_framework = FrontendFramework.REACT_VITE

    @property
    def python_package_name(self) -> str:
        """Get Python-safe package name (underscores)."""
        return self.name.replace("-", "_")

    @property
    def display_name(self) -> str:
        """Get display-friendly name (title case)."""
        return self.name.replace("-", " ").title()

    @property
    def is_monorepo(self) -> bool:
        """Check if this is a monorepo project."""
        return self.project_type == ProjectType.MONOREPO


@dataclass
class TemplateContext:
    """Context for template rendering."""

    config: ProjectConfig
    version: str = "0.9.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for Jinja2 template rendering."""
        return {
            # Project info
            "project_name": self.config.name,
            "project_description": self.config.description
            or f"{self.config.display_name} API",
            "python_package_name": self.config.python_package_name,
            "display_name": self.config.display_name,
            # Type
            "project_type": self.config.project_type.value,
            "is_monorepo": self.config.is_monorepo,
            "frontend_framework": (
                self.config.frontend_framework.value
                if self.config.frontend_framework
                else None
            ),
            # Features
            "use_celery": self.config.use_celery,
            "use_redis": self.config.use_redis,
            "use_docker": self.config.use_docker,
            "auth_methods": [m.value for m in self.config.auth_methods],
            "has_jwt": AuthMethod.JWT in self.config.auth_methods,
            "has_oauth": AuthMethod.OAUTH in self.config.auth_methods,
            "has_otp": AuthMethod.OTP in self.config.auth_methods,
            # Code generation options
            "include_docstrings": self.config.include_docstrings,
            "email_backend": self.config.email_backend.value,
            # Deployment
            "deployment_target": self.config.deployment_target.value,
            "single_container": self.config.single_container,
            # Git
            "init_git": self.config.init_git,
            "git_remote": self.config.git_remote,
            # Author
            "author_name": self.config.author_name,
            "author_email": self.config.author_email,
            # Meta
            "version": self.version,
        }


# Repository URLs for cloning
REPO_URLS = {
    "backend": "https://github.com/mattjaikaran/django-ninja-boilerplate.git",
    "frontend": "https://github.com/mattjaikaran/react-vite-boilerplate.git",
}

# Default branch to clone
DEFAULT_BRANCH = "main"

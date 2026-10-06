"""Tests for the project initialization command."""

from pathlib import Path

from django_ninja_matt.commands import init as init_command
from django_ninja_matt.config import ProjectConfig, ProjectType


def test_run_init_yes_uses_standalone_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Use the standalone layout without opening an interactive prompt."""
    generated: list[ProjectConfig] = []

    monkeypatch.setattr(
        init_command,
        "prompt_project_type",
        lambda: (_ for _ in ()).throw(AssertionError("prompt opened")),
    )
    monkeypatch.setattr(
        init_command,
        "generate_standalone",
        lambda config: generated.append(config) or True,
    )

    init_command.run_init(
        name="example-api",
        path=tmp_path,
        project_type=None,
        deployment=None,
        use_celery=True,
        use_redis=True,
        init_git=False,
        skip_prompts=True,
    )

    assert len(generated) == 1
    assert generated[0].project_type is ProjectType.STANDALONE

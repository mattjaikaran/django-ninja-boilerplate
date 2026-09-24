"""Tests for CLI-driven project setup."""

from pathlib import Path

import questionary

from django_ninja_matt.commands.setup import (
    TaskBackend,
    configure_environment,
    prompt_task_backend,
    read_environment_value,
    run_setup,
)


def write_example(path: Path) -> None:
    (path / ".env.example").write_text(
        "SECRET_KEY=example\nTASK_BACKEND=celery\nCUSTOM=value\n"
    )


def test_configure_environment_creates_env_from_example(tmp_path: Path) -> None:
    write_example(tmp_path)

    env_path = configure_environment(tmp_path, TaskBackend.DRAMATIQ)

    assert env_path.read_text() == (
        "SECRET_KEY=example\nTASK_BACKEND=dramatiq\nCUSTOM=value\n"
    )


def test_configure_environment_preserves_existing_values(tmp_path: Path) -> None:
    write_example(tmp_path)
    (tmp_path / ".env").write_text(
        "SECRET_KEY=installed\nTASK_BACKEND=huey\nCUSTOM=preserved\n"
    )

    configure_environment(tmp_path, TaskBackend.DJANGO_RQ)

    assert (tmp_path / ".env").read_text() == (
        "SECRET_KEY=installed\nTASK_BACKEND=django_rq\nCUSTOM=preserved\n"
    )


def test_read_environment_value_uses_unexported_dotenv_port(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DJANGO_PORT='8010'\n")
    monkeypatch.delenv("DJANGO_PORT", raising=False)

    assert read_environment_value(env_path, "DJANGO_PORT", "8000") == "8010"


def test_read_environment_value_uses_default_for_empty_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DJANGO_PORT=8010\n")
    monkeypatch.setenv("DJANGO_PORT", "")

    assert read_environment_value(env_path, "DJANGO_PORT", "8000") == "8000"


def test_prompt_uses_celery_when_selection_is_skipped(monkeypatch) -> None:
    class Prompt:
        def ask(self):
            return None

    monkeypatch.setattr(questionary, "select", lambda *args, **kwargs: Prompt())

    assert prompt_task_backend() is TaskBackend.CELERY


def test_run_setup_writes_backend_before_bootstrap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_example(tmp_path)
    (tmp_path / "justfile").write_text("setup-services:\n    true\n")
    calls: list[list[str]] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "django_ninja_matt.commands.setup.subprocess.run",
        lambda command, check: calls.append(command),
    )

    run_setup(auto=False, backend=TaskBackend.DJANGO_Q)

    assert "TASK_BACKEND=django_q" in (tmp_path / ".env").read_text()
    assert calls == [["just", "setup-services"]]

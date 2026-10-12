"""Tests for the add-app command."""

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from django_ninja_matt import cli


def test_add_app_runs_project_generator(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    runner = CliRunner()

    outside = runner.invoke(cli.app, ["add-app", "gadgets", "--path", str(tmp_path)])
    assert outside.exit_code == 1
    assert "No manage.py found" in outside.output
    assert calls == []

    (tmp_path / "manage.py").write_text("")
    nested = tmp_path / "api"
    nested.mkdir()

    wired = runner.invoke(cli.app, ["add-app", "gadgets", "--path", str(nested)])
    assert wired.exit_code == 0, wired.output

    monkeypatch.chdir(nested)
    unwired = runner.invoke(cli.app, ["add-app", "gadgets", "--no-wire"])
    assert unwired.exit_code == 0, unwired.output

    root = tmp_path.resolve()
    assert calls == [
        (
            [
                "uv",
                "run",
                "python",
                "manage.py",
                "generate_feature",
                "api_endpoint",
                "--app-name",
                "gadgets",
            ],
            root,
        ),
        (["uv", "run", "python", "manage.py", "startapp_extended", "gadgets"], root),
    ]

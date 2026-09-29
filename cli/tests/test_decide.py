"""Tests for ``dnm decide``."""

import subprocess

import pytest
from typer.testing import CliRunner

from django_ninja_matt.cli import app

runner = CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "manage.py").write_text("")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []
    status = {"code": 0}

    def fake_run(cmd, check):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, status["code"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls, status


def test_gate_runs_agent_decide_in_the_project(project):
    calls, _ = project
    result = runner.invoke(
        app, ["decide", "gate", "rm -rf build", "--environment", "ci"]
    )
    assert result.exit_code == 0
    assert calls == [
        [
            "uv",
            "run",
            "python",
            "manage.py",
            "agent_decide",
            "gate",
            "rm -rf build",
            "--environment",
            "ci",
        ]
    ]


def test_a_handover_status_passes_through(project):
    _, status = project
    status["code"] = 3
    result = runner.invoke(app, ["decide", "route", "Design the billing model"])
    assert result.exit_code == 3


def test_outside_a_project_it_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["decide", "triage"])
    assert result.exit_code == 1

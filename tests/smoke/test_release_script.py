"""Unit tests for the release script (scripts/release.py)."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release.py"
_spec = importlib.util.spec_from_file_location("release", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point the script at a minimal clean tree and record every command."""
    (tmp_path / "api" / "settings").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('version = "1.11.0"\n')
    (tmp_path / "api" / "settings" / "common.py").write_text('default="1.11.0"\n')
    (tmp_path / "justfile").write_text("# v1.11.0\n")
    (tmp_path / "CHANGELOG.md").write_text(
        "## [Unreleased]\n\n[Unreleased]: x\n[1.11.0]: y\n"
    )
    calls: list[list[str]] = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release.subprocess, "run", fake_subprocess_run)
    return tmp_path, calls


@pytest.mark.parametrize("argv", [["--help"], ["--bogus"], ["1.12.0", "--pushh"]])
def test_help_and_unknown_flags_exit_before_any_change(repo, argv):
    root, calls = repo
    with pytest.raises(SystemExit) as exc_info:
        release.main(argv)
    assert exc_info.value.code == (0 if argv == ["--help"] else 2)
    assert calls == []
    assert (root / "pyproject.toml").read_text() == 'version = "1.11.0"\n'


def test_release_tags_locally_without_push(repo):
    root, calls = repo
    release.main(["1.12.0"])
    assert ["git", "tag", "v1.12.0"] in calls
    assert not any(cmd[:2] == ["git", "push"] for cmd in calls)
    assert (root / "VERSION").read_text() == "1.12.0\n"
    assert "## [1.12.0] - " in (root / "CHANGELOG.md").read_text()


def test_push_flag_pushes_after_tag(repo):
    _root, calls = repo
    release.main(["1.12.0", "--push"])
    assert calls[-2:] == [
        ["git", "tag", "v1.12.0"],
        ["git", "push", "origin", "main", "--tags"],
    ]

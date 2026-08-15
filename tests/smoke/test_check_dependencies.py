"""Unit tests for the dependency gate (scripts/check_dependencies.py)."""

import importlib.util
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_dependencies.py"
_spec = importlib.util.spec_from_file_location("check_dependencies", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
_check_dependencies = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_check_dependencies)

evaluate = _check_dependencies.evaluate
file_changed = _check_dependencies.file_changed


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def _commit_all(repo: Path) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_evaluate_passes_when_pyproject_unchanged() -> None:
    passed, _message = evaluate(pyproject_changed=False, dependencies_changed=False)
    assert passed is True


def test_evaluate_passes_when_both_changed() -> None:
    passed, _message = evaluate(pyproject_changed=True, dependencies_changed=True)
    assert passed is True


def test_evaluate_fails_when_pyproject_changed_without_manifest() -> None:
    passed, message = evaluate(pyproject_changed=True, dependencies_changed=False)
    assert passed is False
    assert "DEPENDENCIES.md" in message


def test_file_changed_false_when_unchanged(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", "[project]\n")
    _commit_all(tmp_path)

    assert file_changed(tmp_path, Path("pyproject.toml")) is False


def test_file_changed_detects_modification(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", "[project]\n")
    _commit_all(tmp_path)
    _write(tmp_path / "pyproject.toml", "[project]\ndependencies = ['a']\n")

    assert file_changed(tmp_path, Path("pyproject.toml")) is True


def test_file_changed_detects_new_untracked_file(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", "[project]\n")
    _commit_all(tmp_path)
    _write(tmp_path / "DEPENDENCIES.md", "# Dependencies\n")

    assert file_changed(tmp_path, Path("DEPENDENCIES.md")) is True


def test_file_changed_false_for_missing_file_absent_from_head(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", "[project]\n")
    _commit_all(tmp_path)

    assert file_changed(tmp_path, Path("DEPENDENCIES.md")) is False


def test_version_only_change_passes(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", '[project]\nversion = "1.0.0"\n')
    _commit_all(tmp_path)

    _write(tmp_path / "pyproject.toml", '[project]\nversion = "1.1.0"\n')

    assert (
        _check_dependencies.version_only_change(tmp_path, Path("pyproject.toml"))
        is True
    )


def test_version_only_change_fails_on_dependency_change(tmp_path: Path) -> None:
    _git_init(tmp_path)
    _write(tmp_path / "pyproject.toml", '[project]\nversion = "1.0.0"\n')
    _commit_all(tmp_path)

    _write(
        tmp_path / "pyproject.toml",
        '[project]\nversion = "1.1.0"\ndependencies = ["requests"]\n',
    )

    assert (
        _check_dependencies.version_only_change(tmp_path, Path("pyproject.toml"))
        is False
    )

"""Keep nonblocking findings distinct from passed and failed gates."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def gauntlet_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    # The script changes cwd on import; restore it at the fixture boundary.
    monkeypatch.chdir(tmp_path)
    path = Path(__file__).resolve().parents[2] / "scripts" / "gauntlet.py"
    spec = importlib.util.spec_from_file_location("gauntlet_result_probe", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_warning_is_not_reported_as_passed(gauntlet_module: ModuleType) -> None:
    runner = gauntlet_module.GauntletRunner()
    result = runner.run_gate(
        "OPTIONAL", [sys.executable, "-c", "raise SystemExit(7)"], allow_fail=True
    )
    assert result.passed is False
    assert result.warning is True
    assert runner._print_summary(0) is True
    report = runner.generate_report()
    assert report["all_passed"] is False
    assert report["blocking_passed"] is True
    assert report["has_warnings"] is True
    assert report["gates"][0]["passed"] is False
    assert report["gates"][0]["warning"] is True


def test_blocking_failure_still_fails_with_warnings(
    gauntlet_module: ModuleType,
) -> None:
    runner = gauntlet_module.GauntletRunner()
    command = [sys.executable, "-c", "raise SystemExit(7)"]
    runner.run_gate("OPTIONAL", command, allow_fail=True)
    failed = runner.run_gate("REQUIRED", command)
    assert failed.passed is False
    assert failed.warning is False
    assert runner._print_summary(0) is False
    report = runner.generate_report()
    assert report["all_passed"] is False
    assert report["blocking_passed"] is False
    assert report["has_warnings"] is True

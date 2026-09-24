"""Tests for the seed_decisions management command."""

import pytest
from django.core.management import call_command

from decisions.models import DecisionFixture

#: Number of fixtures shipped in decisions/data/fixtures.
SHIPPED_FIXTURE_COUNT = 7


@pytest.mark.django_db
class TestSeedDecisionsCommand:
    """The command loads the shipped fixtures and is idempotent."""

    def test_seeds_shipped_fixtures(self, capsys):
        call_command("seed_decisions")
        assert DecisionFixture.objects.count() == SHIPPED_FIXTURE_COUNT
        assert f"{SHIPPED_FIXTURE_COUNT} created" in capsys.readouterr().out

    def test_second_run_updates_in_place(self, capsys):
        call_command("seed_decisions")
        call_command("seed_decisions")
        assert DecisionFixture.objects.count() == SHIPPED_FIXTURE_COUNT
        assert f"{SHIPPED_FIXTURE_COUNT} updated" in capsys.readouterr().out

    def test_missing_directory_reports_error(self, capsys, tmp_path):
        call_command("seed_decisions", dir=str(tmp_path / "absent"))
        assert "Fixture directory not found" in capsys.readouterr().err

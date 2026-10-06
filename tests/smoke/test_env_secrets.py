"""Tests for the .env secret generator and its guard check."""

import importlib.util
import json
import stat
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, _ROOT / "scripts" / f"{name}.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


env_secrets = _load("env_secrets")
check_env_secrets = _load("check_env_secrets")

TEMPLATE = (
    "SECRET_KEY=your-secret-key-here-change-in-production\n"
    "DB_PASSWORD=postgres\n"
    "CENTRIFUGO_API_KEY=dev-centrifugo-api-key\n"
    "# NEO4J_PASSWORD=\n"
    "DEBUG=1\n"
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".env.example").write_text(TEMPLATE)
    (tmp_path / ".gitignore").write_text("*.pyc\n.env.*\n!.env.example\n")
    return tmp_path


def test_create_generates_every_secret_privately(project: Path) -> None:
    env_path = project / ".env"

    names = env_secrets.create_env(
        env_path, project / ".env.example", overrides={"DEBUG": "0"}
    )

    values = env_secrets.read_env(env_path)
    generated = [values[secret.name] for secret in env_secrets.SECRETS]
    assert names == list(env_secrets.NAMES)
    assert len(set(generated)) == len(generated)
    assert not env_secrets.weak_secrets(env_path)
    assert values["DEBUG"] == "0"
    assert "# NEO4J_PASSWORD=" not in env_path.read_text()
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert ".env" in (project / ".gitignore").read_text().splitlines()


def test_create_without_template_writes_only_selected_secrets(project: Path) -> None:
    env_path = project / ".env.production"

    exclude = "NEO4J_PASSWORD,DJANGO_MCP_AUTH_TOKEN"
    exit_code = env_secrets.main(
        ["create", "--env-file", str(env_path), "--no-template", "--exclude", exclude]
    )

    values = env_secrets.read_env(env_path)
    assert exit_code == 0
    assert set(values) == set(env_secrets.NAMES) - {
        "NEO4J_PASSWORD",
        "DJANGO_MCP_AUTH_TOKEN",
    }
    # .env.* is already ignored, so .gitignore keeps its three lines.
    assert len((project / ".gitignore").read_text().splitlines()) == 3


def test_create_never_replaces_existing_env(project: Path) -> None:
    (project / ".env").write_text("SECRET_KEY=mine\n")

    exit_code = env_secrets.main(["create", "--root", str(project)])

    assert exit_code == 1
    assert (project / ".env").read_text() == "SECRET_KEY=mine\n"


def test_fill_replaces_placeholders_but_keeps_chosen_and_stored_values(
    project: Path,
) -> None:
    env_path = project / ".env"
    env_path.write_text(
        "SECRET_KEY=same-key-same-key-same-key-same-key-same-key-same-key\n"
        "NINJA_JWT_SIGNING_KEY=same-key-same-key-same-key-same-key-same-key-same-key\n"
        "DB_PASSWORD=postgres\n"
        "SUPERUSER_PASSWORD=short\n"
        "CENTRIFUGO_API_KEY=dev-centrifugo-api-key\n"
    )

    filled, skipped = env_secrets.fill_env(env_path)

    values = env_secrets.read_env(env_path)
    assert values["SECRET_KEY"].startswith("same-key")
    assert values["NINJA_JWT_SIGNING_KEY"] != values["SECRET_KEY"]
    assert values["DB_PASSWORD"] == "postgres"
    assert values["SUPERUSER_PASSWORD"] == "short"
    assert values["CENTRIFUGO_API_KEY"] != "dev-centrifugo-api-key"
    # Missing stored secrets are generated; set placeholders are not.
    assert "NEO4J_PASSWORD" in filled
    assert skipped == ["DB_PASSWORD"]
    assert set(env_secrets.weak_secrets(env_path)) == {
        "DB_PASSWORD",
        "SUPERUSER_PASSWORD",
    }


def test_list_json_describes_every_secret(capsys: pytest.CaptureFixture[str]) -> None:
    env_secrets.main(["list", "--json"])

    listed = json.loads(capsys.readouterr().out)
    assert listed["version"] == 1
    assert [item["name"] for item in listed["secrets"]] == list(env_secrets.NAMES)
    flower = next(i for i in listed["secrets"] if i["name"] == "FLOWER_BASIC_AUTH")
    assert flower["kind"] == "basic_auth"


def test_every_guarded_secret_is_generated() -> None:
    assert check_env_secrets.find_problems(_ROOT) == []


def test_env_secrets_doc_lists_exactly_the_generated_secrets() -> None:
    doc = (_ROOT / "docs" / "ENV_SECRETS.md").read_text()
    variables = doc.split("## Variables", 1)[1].split("\n## ", 1)[0]
    documented = {
        line.split("`")[1] for line in variables.splitlines() if line.startswith("| `")
    }

    assert documented == set(env_secrets.NAMES)

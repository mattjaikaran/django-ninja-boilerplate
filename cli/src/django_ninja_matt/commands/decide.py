"""``dnm decide``: local typed decisions for coding agents and developers.

Every sub-command runs a ``manage.py`` command in the current project with
``uv run``, so it uses the project's ``SYSTEMONE_PROVIDER`` and
``DECISION_THRESHOLDS_FILE``. The exit status is passed through: ``3`` means
the decision hands over (``escalate`` or ``ask_human``), so a git hook or an
agent script can stop and ask.
"""

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from django_ninja_matt.utils.console import print_error

decide_app = typer.Typer(
    help=(
        "Answer cheap, typed questions with the local decision engine before "
        "you call a large model."
    ),
    no_args_is_help=True,
)


def manage_command(args: list[str]) -> list[str]:
    """Return the argv that runs ``manage.py`` with *args* through uv."""
    return ["uv", "run", "python", "manage.py", *args]


def run_manage(args: list[str]) -> None:
    """Run ``manage.py`` with *args* and exit with its status."""
    if not Path("manage.py").is_file():
        print_error("manage.py not found. Run dnm decide from the project root.")
        raise typer.Exit(1)
    try:
        result = subprocess.run(manage_command(args), check=False)
    except FileNotFoundError:
        print_error("uv not found. Install it from https://docs.astral.sh/uv/.")
        raise typer.Exit(1) from None
    if result.returncode:
        raise typer.Exit(result.returncode)


@decide_app.command()
def route(
    task: Annotated[
        str, typer.Argument(help="The coding task, as you would write it.")
    ],
    files_hint: Annotated[
        str, typer.Option(help="Files or areas the task names.")
    ] = "",
) -> None:
    """Pick the cheapest capable model tier for a task."""
    args = ["agent_decide", "route", task]
    if files_hint:
        args += ["--files-hint", files_hint]
    run_manage(args)


@decide_app.command()
def triage(
    commit: Annotated[str, typer.Option(help="Git revision to triage.")] = "HEAD",
) -> None:
    """Classify a commit and choose its review depth."""
    run_manage(["agent_decide", "triage", "--commit", commit])


@decide_app.command()
def gate(
    action: Annotated[str, typer.Argument(help="The command or action to check.")],
    environment: Annotated[
        str, typer.Option(help="local, ci, staging, or production.")
    ] = "local",
    reason: Annotated[str, typer.Option(help="Why the action is needed.")] = "",
) -> None:
    """Check whether an action may run without human approval."""
    args = ["agent_decide", "gate", action, "--environment", environment]
    if reason:
        args += ["--reason", reason]
    run_manage(args)


@decide_app.command()
def generator(
    request: Annotated[str, typer.Argument(help="What you want to build.")],
    app_name: Annotated[str, typer.Option(help="App name for the command.")] = "",
) -> None:
    """Pick the generate_feature generator for a feature request."""
    args = ["agent_decide", "generator", request]
    if app_name:
        args += ["--app-name", app_name]
    run_manage(args)


@decide_app.command("eval")
def evaluate(
    provider: Annotated[str, typer.Option(help="Provider to evaluate.")] = "",
    output: Annotated[str, typer.Option(help="Report path.")] = "",
    skip_unavailable: Annotated[
        bool, typer.Option(help="Record an unavailable provider as skipped.")
    ] = False,
) -> None:
    """Evaluate a provider on the bundled benchmark."""
    args = ["eval_decisions", "--benchmark"]
    if provider:
        args += ["--provider", provider]
    if output:
        args += ["--output", output]
    if skip_unavailable:
        args.append("--skip-unavailable")
    run_manage(args)


@decide_app.command()
def compare(
    reports: Annotated[list[str], typer.Argument(help="Report JSON paths.")],
) -> None:
    """Compare saved eval reports on the held-out test split."""
    run_manage(["compare_decisions", *reports])

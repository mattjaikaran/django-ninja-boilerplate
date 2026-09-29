"""Ask a typed agent decision from the command line and print JSON.

Examples::

    python manage.py agent_decide route "Rename get_user to fetch_user in core/"
    python manage.py agent_decide triage --commit HEAD
    python manage.py agent_decide gate "docker volume rm app_pg" --environment local
    python manage.py agent_decide generator "Let users upload avatars" --app-name avatars

The command uses ``SYSTEMONE_PROVIDER`` and ``DECISION_THRESHOLDS_FILE``,
the same as the API and MCP tools. It exits with status 3 when the
decision's ``next_step`` is ``escalate`` or ``ask_human``, so a script or
hook can stop and hand over. A provider error exits with status 1.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from api.exceptions import ValidationError
from decisions.services.agent_service import AgentDecision, AgentDecisionService
from decisions.services.git_changes import commit_state

#: Exit status when the decision hands over to a stronger model or a person.
HANDOVER_EXIT = 3

#: Steps that hand over instead of acting.
HANDOVER_STEPS = frozenset({"escalate", "ask_human"})


class Command(BaseCommand):
    """Route a task, triage a change, gate an action, or pick a generator."""

    help = "Answer an agent workflow question with the local decision engine"

    def add_arguments(self, parser) -> None:
        """Add one subcommand per decision pack."""
        sub = parser.add_subparsers(dest="pack", required=True)
        route = sub.add_parser("route", help="Pick a model tier for a coding task")
        route.add_argument("task")
        route.add_argument("--files-hint", default="")
        triage = sub.add_parser("triage", help="Triage a commit or a described change")
        triage.add_argument("title", nargs="?", default="")
        triage.add_argument("--commit", help="Read the change from this git revision")
        triage.add_argument("--description", default="")
        triage.add_argument("--files", nargs="*", default=[])
        gate = sub.add_parser("gate", help="Decide whether an action needs approval")
        gate.add_argument("action")
        gate.add_argument(
            "--environment",
            choices=["local", "ci", "staging", "production"],
            default="local",
        )
        gate.add_argument("--reason", default="")
        generator = sub.add_parser(
            "generator", help="Pick a generate_feature generator"
        )
        generator.add_argument("request")
        generator.add_argument("--app-name", default="")

    def _decide(self, service: AgentDecisionService, options) -> AgentDecision:
        pack = options["pack"]
        if pack == "route":
            return service.route_task(options["task"], options["files_hint"])
        if pack == "gate":
            return service.gate_action(
                options["action"], options["environment"], options["reason"]
            )
        if pack == "generator":
            return service.pick_generator(options["request"], options["app_name"])
        if options["commit"]:
            state = commit_state(options["commit"], Path(settings.BASE_DIR))
            return service.triage_change(**state)
        if not options["title"]:
            raise CommandError("Pass a title or --commit.")
        return service.triage_change(
            options["title"], options["description"], options["files"]
        )

    def handle(self, *args, **options) -> None:
        """Print the decision as JSON and exit 3 on a handover step."""
        try:
            decision = self._decide(AgentDecisionService(), options)
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(decision.as_dict(), indent=2))
        if decision.next_step in HANDOVER_STEPS:
            raise SystemExit(HANDOVER_EXIT)

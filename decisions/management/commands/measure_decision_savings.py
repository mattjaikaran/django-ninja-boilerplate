"""Measure LLM tokens saved by answering typed questions locally.

Examples::

    python manage.py measure_decision_savings --git v1.11.0..HEAD --output reports/triage.json
    python manage.py measure_decision_savings --roadmap ROADMAP.md
    python manage.py measure_decision_savings --benchmark risk_flags --split test
    python manage.py measure_decision_savings --jsonl flows.jsonl --pack gate_action

Each item goes to the decision engine and to the baseline LLM
(``DECISION_BASELINE_LLM_URL``). Token counts are the LLM's reported usage.
The report compares an LLM-only flow with a hybrid flow that sends only
escalated items to the LLM. Set ``DECISION_LLM_INPUT_PRICE_PER_MTOK`` and
``DECISION_LLM_OUTPUT_PRICE_PER_MTOK`` to add cost.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from api.exceptions import ValidationError
from decisions.providers import PROVIDER_REGISTRY
from decisions.services.agent_service import PACK_DOMAINS
from decisions.services.eval_dataset import BENCHMARK_DIR, load_cases
from decisions.services.git_changes import commit_state, commits_in_range
from decisions.services.savings_service import (
    DecisionSavingsService,
    FlowItem,
    roadmap_tasks,
)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


class Command(BaseCommand):
    """Compare LLM-only and hybrid token use on one flow."""

    help = "Measure LLM tokens saved by local typed decisions"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--git", help="Triage every commit in this revision range")
        source.add_argument("--roadmap", help="Route every task row of a ROADMAP.md")
        source.add_argument(
            "--benchmark",
            choices=sorted(PACK_DOMAINS.values()),
            help="Labelled benchmark domain",
        )
        source.add_argument("--jsonl", help="JSONL of {id, state, expected?} items")
        parser.add_argument(
            "--pack", choices=sorted(PACK_DOMAINS), help="Pack for --jsonl input"
        )
        parser.add_argument("--split", help="Benchmark split to use")
        parser.add_argument(
            "--limit", type=int, default=0, help="Use the first N items"
        )
        parser.add_argument(
            "--provider",
            choices=sorted(PROVIDER_REGISTRY),
            help="Engine provider. Defaults to SYSTEMONE_PROVIDER.",
        )
        parser.add_argument("--output", help="Write the JSON report to this path")

    def _flow(self, options) -> tuple[str, list[FlowItem], str]:
        if options["git"]:
            root = Path(settings.BASE_DIR)
            revs = commits_in_range(options["git"], root, options["limit"])
            items = [FlowItem(rev[:10], commit_state(rev, root)) for rev in revs]
            return "triage_change", items, f"git {options['git']}"
        if options["roadmap"]:
            return (
                "route_task",
                roadmap_tasks(Path(options["roadmap"])),
                options["roadmap"],
            )
        if options["benchmark"]:
            domain = options["benchmark"]
            pack = next(p for p, d in PACK_DOMAINS.items() if d == domain)
            cases = load_cases(BENCHMARK_DIR / domain, split=options["split"])
            items = [FlowItem(c.case_id, c.state, c.expected) for c in cases]
            return pack, items, f"benchmark {domain} {options['split'] or 'all'}"
        if not options["pack"]:
            raise CommandError("--jsonl needs --pack.")
        rows = [
            json.loads(line)
            for line in Path(options["jsonl"]).read_text().splitlines()
            if line.strip()
        ]
        items = [
            FlowItem(str(r.get("id", i + 1)), r["state"], r.get("expected"))
            for i, r in enumerate(rows)
        ]
        return options["pack"], items, options["jsonl"]

    def handle(self, *args, **options) -> None:
        """Run the flow and print the summary."""
        try:
            pack, items, source = self._flow(options)
            if options["limit"]:
                items = items[: options["limit"]]
            if not items:
                raise CommandError(f"The flow '{source}' has no items.")
            service = DecisionSavingsService(provider=options["provider"])
            data = service.measure(pack, items, source).as_dict()
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
        if options["output"]:
            Path(options["output"]).parent.mkdir(parents=True, exist_ok=True)
            Path(options["output"]).write_text(json.dumps(data, indent=2) + "\n")
        tokens = data["tokens"]
        llm_only = tokens["llm_only"]["prompt"] + tokens["llm_only"]["completion"]
        hybrid = tokens["hybrid"]["prompt"] + tokens["hybrid"]["completion"]
        self.stdout.write(
            f"{source}: {data['items']} items, pack {pack}, engine {data['provider']}, "
            f"baseline {data['baseline_model']}\n"
            f"items resolved locally: {data['resolved_locally']} "
            f"({_pct(data['local_rate'])}); answers answered locally: "
            f"{_pct(data['local_answer_share'])}\n"
            f"LLM tokens: LLM only {llm_only}, hybrid {hybrid}, saved "
            f"{tokens['saved']} ({_pct(tokens['saved_share'])})\n"
            f"cost USD: LLM only {data['cost_usd']['llm_only']}, "
            f"hybrid {data['cost_usd']['hybrid']}\n"
            f"engine and LLM agree on local answers: {_pct(data['agreement_on_local'])}\n"
            f"accuracy: LLM only {_pct(data['accuracy']['llm_only'])}, "
            f"hybrid {_pct(data['accuracy']['hybrid'])}\n"
            f"baseline replies that were not valid answers: {data['baseline_invalid']}\n"
            f"latency p50: engine {data['latency_ms']['engine_p50']:.0f} ms, "
            f"LLM {data['latency_ms']['baseline_p50']:.0f} ms"
        )

"""One-line fix hints for each gauntlet gate.

`scripts/gauntlet.py` prints the hint of every failed gate in its summary and
writes it to the JSON report as `fix_hint`, so an agent knows the first thing
to try without reading the gate's full output.
"""

from __future__ import annotations

FIX_HINTS: dict[str, str] = {
    "FORMAT": "Run `just fmt` (ruff format), then re-run the gate.",
    "LINT": "Run `uv run ruff check --fix .`; fix what remains by hand.",
    "TYPECHECK": "Run `uv run mypy <file>` on the files you changed; add hints.",
    "SECURITY": "Read the bandit finding; fix it. `# nosec` needs a written reason.",
    "CONVENTIONS": "Run `just check-conventions`; each line names the rule and fix.",
    "DEPENDENCIES": "Add an entry to DEPENDENCIES.md for the pyproject.toml change.",
    "DRIFT": "Run `just check-drift`; align the versions it lists.",
    "ARCHITECTURE": "Run `just check-arch`; move the import to the right layer.",
    "OPENAPI": "Run `just openapi` and commit docs/openapi/openapi.json.",
    "SCHEMA-PARITY": "Use camelCase aliases and typed fields in the schema it names.",
    "FILELENGTH": "Split the file it names; do not raise the cap.",
    "CROSS-STACK": "Monorepo only: run `just check-cross-stack` for details.",
    "JOURNEYS": "Run `just check-journeys`; see docs/product/README.md.",
    "TICKETS": "Run `just tickets check`; see docs/tickets/README.md.",
    "TEST": "Run `just test <file>` on the failing test; read its assertion.",
    "TEST-OPTIONAL": "Run `just test-optional` (webhooks and files apps).",
    "CLI-TEST": "Run `uv run --project cli pytest cli/tests -x`.",
    "AI-DB": "Run `just test-ai-db`; it needs Docker and pgvector.",
    "DEPLOY-CHECK": "Read the Django check IDs; prod settings fix most of them.",
    "AUDIT": "Upgrade the package, or allow-list it with a reason and expiry.",
    "DOCKER": "Run `docker build .` and read the first failing step.",
    "GENERATORS": "Run `just check-generators`; it names the generator and step.",
}

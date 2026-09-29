# Decisions for agents

This page describes the agent decision packs: typed questions that a coding
agent or a developer tool can answer with the local decision engine before it
calls a large model. It also reports the measured token savings. Read
[Decision provider benchmark](DECISIONS_BENCHMARK.md) first for the accuracy
of each question.

## Summary

- Four packs: route a task to a model tier, triage a change, gate an action,
  and pick a `generate_feature` generator.
- The engine answers each question locally. An answer that meets its
  per-question threshold stays local. A weak answer escalates, and the caller
  sends only the weak questions to a stronger model or a person.
- On this host, a small local LLM is the cheap tier. The baseline,
  Qwen3-4B-Instruct in llama.cpp, beat Laya on every pack. Laya scored 34.1%
  on `tier`; the 4B model scored 73.2% on the whole routing pack.
- With the shipped thresholds, which only keep rows that held on the
  held-out test split, Laya saved tokens on one pack: 15.2% on `risk_flags`,
  at 78.6% hybrid accuracy against 81.7% for LLM only. Every other pack
  escalated every question, so it saved nothing.
- `route_task` has no evidence behind it yet. Both providers scored at or
  below the most-common-label rate on `tier`.

## Packs

Each pack reads its questions from the benchmark domain that measures it
(`decisions/data/benchmark/<domain>/questions.json`). Thresholds tuned on that
domain apply to exactly the questions the pack asks.

| Pack | Domain | Questions | `next_step` |
|---|---|---|---|
| `route_task` | `task_routing` | `tier`, `needs_human` | `use_local`, `use_mid`, `use_frontier`, `ask_human`, `escalate` |
| `triage_change` | `code_review_triage` | `change_type`, `needs_migration_review`, `security_sensitive` | `deep_review`, `standard_review`, `escalate` |
| `gate_action` | `risk_flags` | `destructive`, `needs_approval`, `scope` | `allow`, `ask_human` |
| `pick_generator` | `generator_choice` | `generator` | `generate` (with the command), `escalate` |

Rules:

- `escalate` means at least one answer is below its threshold.
  `escalated_questions` names them. Send those questions to a stronger model
  or a person. The service never answers with a different provider.
- `gate_action` fails closed. It returns `ask_human`, with the reasons in
  `details.reasons`, when any of these is true:
  - an answer is below its threshold (`uncertain`);
  - the model says the action is destructive or needs approval;
  - the model says the scope is `production`;
  - the caller's `environment` is not `local` (`environment:<name>`). This
    rule does not depend on the model;
  - `DECISION_THRESHOLDS_FILE` has no threshold for one of the three gate
    questions for the active provider (`uncalibrated`). The global
    `DECISION_ESCALATION_THRESHOLD` alone never allows an action.

  `environment` must be `local`, `ci`, `staging`, or `production`. The
  service rejects other values, so the HTTP, MCP, and CLI surfaces get the
  same check. Treat `allow` as a first filter, not as permission: your own
  policy for production and irreversible actions still applies. With the
  shipped thresholds, Laya's `destructive` and `needs_approval` are 1.0, so
  the gate never returns `allow` for Laya.
- `pick_generator` returns the command to run, for example
  `uv run python manage.py generate_feature file_storage --app-name uploads`.
  It does not run it. `app_name` must be a lowercase identifier.
- The server selects the provider (`SYSTEMONE_PROVIDER`) and the thresholds
  (`DECISION_THRESHOLDS_FILE`). No caller can set either.

## Surfaces

| Surface | How to call it |
|---|---|
| HTTP (JWT) | `POST /api/decisions/agent/route-task`, `/triage-change`, `/gate-action`, `/pick-generator` |
| MCP | `route_agent_task`, `triage_change`, `gate_agent_action`, `pick_generator` (with `just up-mcp`) |
| CLI | `dnm decide route "<task>"`, `dnm decide triage --commit HEAD`, `dnm decide gate "<cmd>" --environment local`, `dnm decide generator "<request>"` |
| just | `just decide route "<task>"`, `just decide triage --commit HEAD` |
| Python | `AgentDecisionService().gate_action("git push --force", "local")` |

Git revisions are read only by the CLI and the management commands, never
from HTTP or MCP callers. A revision that starts with `-` is rejected.

The CLI prints the decision as JSON. It exits with status 3 for `escalate` or
`ask_human`, so a git hook or an agent script can stop. Measured on this
repository with Laya and the shipped thresholds:

```text
$ dnm decide triage --commit 81d2d1e      # "next_step": "escalate"
dnm triage exit=3
$ python manage.py agent_decide gate "drop table users" --environment production
manage.py gate exit=3                      # reasons: uncertain, destructive,
                                           # production, environment:production
```

## Measure token savings

`measure_decision_savings` (`just decisions-savings`) runs a flow through the
engine and through a baseline LLM, and compares two flows from the LLM's
reported token usage:

- **LLM only**: every question goes to the LLM.
- **Hybrid**: answers that meet their threshold stay local. The LLM gets only
  the escalated questions, with the same state. A partial call still resends
  the system prompt and the state, so savings are less than proportional.

When items have labels, the report also compares the accuracy of both flows.

```bash
export DECISION_BASELINE_LLM_URL=http://127.0.0.1:8092/v1/chat/completions
export DECISION_BASELINE_LLM_MODEL=qwen3-4b-instruct-2507
just decisions-savings --git v1.11.0..HEAD --output reports/savings/commits.json
just decisions-savings --roadmap ROADMAP.md
just decisions-savings --benchmark risk_flags --split test
just decisions-savings --jsonl flows.jsonl --pack gate_action
```

Set `DECISION_LLM_INPUT_PRICE_PER_MTOK` and
`DECISION_LLM_OUTPUT_PRICE_PER_MTOK` to add cost. Without prices, the report
shows tokens only.

### Measured results

Setup: Apple M2 Pro, 32 GB, 2026-09-29. Engine: Laya 0.3.11, in-process.
Baseline LLM: Qwen3-4B-Instruct-2507 Q4_K_M in llama.cpp 0.5.0 (build
11146), temperature 0, on the same host. Token counts are the `usage` values
that llama.cpp returned, from the Qwen3 tokenizer. The per-item reports are in
`docs/decisions/reports/savings/`.

**With the shipped thresholds** (`decisions/data/thresholds.example.json`,
only rows that held on the test split). These rows are recomputed from the
recorded per-item measurements: for each item, the recorded Laya confidences
decide which questions stay local, and the recorded LLM calls supply the
tokens and answers. No new model call was made.

| Flow | Items | Answers kept local | LLM-only tokens | Hybrid tokens | Saved | Accuracy, LLM only | Accuracy, hybrid |
|---|---|---|---|---|---|---|---|
| Commits `v1.11.0..HEAD` (real) | 45 | 0% | 26,422 | 26,422 | 0% | not labelled | not labelled |
| ROADMAP.md tasks (real) | 134 | 0% | 47,064 | 47,064 | 0% | not labelled | not labelled |
| `code_review_triage` test | 43 | 0% | 20,106 | 20,106 | 0% | 88.4% | 88.4% |
| `task_routing` test | 41 | 0% | 15,198 | 15,198 | 0% | 73.2% | 73.2% |
| `risk_flags` test | 42 | 22.2% | 16,573 | 14,053 | 15.2% | 81.7% | 78.6% |
| `generator_choice` test | 30 | 0% | 11,174 | 11,174 | 0% | 93.3% | 93.3% |

**With an earlier thresholds file that is now withdrawn** (measured
directly). It kept Laya's `change_type` at 0.10 and `generator` at 0.90,
which scored 79.5% and 76.5% on test against a 90% target:

| Flow | Saved | Accuracy, LLM only | Accuracy, hybrid |
|---|---|---|---|
| Commits `v1.11.0..HEAD` | 21.8% | not labelled | not labelled |
| `code_review_triage` test | 29.4% | 88.4% | 89.9% |
| `risk_flags` test | 19.0% | 81.7% | 78.6% |
| `generator_choice` test | 56.7% | 93.3% | 86.7% |

Those savings came from thresholds that failed their held-out check, so do
not rely on them.

**With no thresholds file** (every answer at or above 0.5 stays local,
measured directly):

| Flow | Answers kept local | Saved | Accuracy, LLM only | Accuracy, hybrid |
|---|---|---|---|---|
| `code_review_triage` test | 69.8% | 42.2% | 88.4% | 64.3% |
| `task_routing` test | 50.0% | 24.3% | 73.2% | 56.1% |
| `risk_flags` test | 88.9% | 82.5% | 81.7% | 64.3% |
| `generator_choice` test | 86.7% | 86.7% | 93.3% | 83.3% |

### What the results show

- **A small local LLM is the cheap tier on this host.** The 4B baseline beat
  Laya on every pack, at 0.7 to 1.3 s p50 per item against 0.06 to 0.28 s for
  Laya. Route questions the engine cannot answer to a small local model before
  a frontier model.
- **System One adds value only where it is calibrated.** With thresholds that
  held on test, Laya kept only `scope` answers local, and the saving on the
  gate pack cost 3.1 points of accuracy.
- **Loose thresholds buy tokens with accuracy.** Without a thresholds file,
  the hybrid flow saves more tokens and loses 10 to 24 points of accuracy.
- **These prompts are minimal.** The baseline prompt holds only the state and
  the typed questions. An agent that asks the same question inside a long
  session sends much more context. That was not measured.

### Caveats

- Cost was not measured. Both models ran locally at no API cost, and no
  hosted LLM key was available. A dollar figure needs a frontier model's
  price and would be an extrapolation, not a measurement.
- Token counts use the Qwen3 tokenizer. A hosted model's tokenizer gives
  different counts for the same text.
- The thresholds were tuned on 20 to 24 `dev` answers per question.
- The shipped-threshold table is recomputed, not re-run. It assumes the LLM
  gives the same tokens and answers for the same prompt at temperature 0; the
  recomputed LLM-only accuracy matches the measured value on every labelled
  flow.
- Later runs were faster (for example, 0.29 s against 0.82 s LLM p50 on
  routing), probably from llama.cpp prompt caching. Compare latency only
  within one run.
- The benchmark flows are synthetic. The commit and ROADMAP flows are real
  but have no labels.

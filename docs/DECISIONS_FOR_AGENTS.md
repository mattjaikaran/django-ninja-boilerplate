# Decisions for agents

This page describes the agent decision packs: typed questions that a coding
agent or a developer tool can answer with the local decision engine before it
calls a large model. It also reports the measured token savings. Read
[Decision provider benchmark](DECISIONS_BENCHMARK.md) first for the accuracy
of each question.

## Summary

- Four packs: route a task to a model tier, triage a change, gate an action,
  and pick a `generate_feature` generator.
- The engine answers each question locally. Answers that meet their
  per-question threshold stay local. Weak answers escalate: the caller sends
  only those questions to a stronger model or a person.
- Measured with Laya and the example thresholds, the hybrid flow saved 21.8%
  of LLM tokens on this repository's 45 commits since v1.11.0, 29.4% on the
  code-review benchmark (accuracy 89.9% against 88.4% for LLM only), and
  56.7% on generator choice (accuracy 86.7% against 93.3%).
- Task routing saved nothing: Laya's `tier` and `needs_human` answers never
  met their thresholds, so every routing question went to the LLM. The
  baseline 4B model scored 73.2% on routing; Laya scored 34.1%.

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
- `gate_action` fails closed. An uncertain answer, a destructive action, an
  action that needs approval, or a production scope gives `ask_human`, with
  the reasons in `details.reasons`. Treat `allow` as a first filter, not as
  permission: your own policy for production and irreversible actions still
  applies.
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

The CLI prints the decision as JSON. It exits with status 3 for `escalate` or
`ask_human`, so a git hook or an agent script can stop:

```bash
dnm decide gate "docker volume rm app_postgres_data" || echo "ask a person"
```

Example response from the live endpoint, with Laya and
`decisions/data/thresholds.example.json`:

```json
{
  "pack": "gate_action",
  "provider": "laya",
  "nextStep": "ask_human",
  "resolvedLocally": false,
  "answers": {"destructive": 0.7615, "needs_approval": 0.4883, "scope": "local"},
  "answerConfidence": {"destructive": 0.7615, "needs_approval": 0.5117, "scope": 0.1653},
  "escalatedQuestions": ["destructive", "needs_approval", "scope"],
  "details": {"reasons": ["uncertain", "destructive"]}
}
```

## Measure token savings

`measure_decision_savings` (`just decisions-savings`) runs a flow through the
engine and through a baseline LLM, and compares two flows from the LLM's
reported token usage:

- **LLM only**: every question goes to the LLM.
- **Hybrid**: answers that meet their threshold stay local. The LLM gets only
  the escalated questions, with the same state.

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
that llama.cpp returned. The full reports are in
`docs/decisions/reports/savings/`.

With the tuned example thresholds (`decisions/data/thresholds.example.json`,
90% target):

| Flow | Items | Answers kept local | LLM-only tokens | Hybrid tokens | Saved | Accuracy, LLM only | Accuracy, hybrid |
|---|---|---|---|---|---|---|---|
| Commits `v1.11.0..HEAD` (real) | 45 | 28.1% | 26,422 | 20,661 | 21.8% | not labelled | not labelled |
| ROADMAP.md tasks (real) | 134 | 0% | 47,064 | 47,064 | 0% | not labelled | not labelled |
| `code_review_triage` test | 43 | 30.2% | 20,106 | 14,201 | 29.4% | 88.4% | 89.9% |
| `task_routing` test | 41 | 0% | 15,198 | 15,198 | 0% | 73.2% | 73.2% |
| `risk_flags` test | 42 | 27.8% | 16,573 | 13,423 | 19.0% | 81.7% | 78.6% |
| `generator_choice` test | 30 | 56.7% | 11,174 | 4,841 | 56.7% | 93.3% | 86.7% |

With no thresholds file (every answer at or above 0.5 stays local):

| Flow | Answers kept local | Saved | Accuracy, LLM only | Accuracy, hybrid |
|---|---|---|---|---|
| `code_review_triage` test | 69.8% | 42.2% | 88.4% | 64.3% |
| `task_routing` test | 50.0% | 24.3% | 73.2% | 56.1% |
| `risk_flags` test | 88.9% | 82.5% | 81.7% | 64.3% |
| `generator_choice` test | 86.7% | 86.7% | 93.3% | 83.3% |

On the 45 real commits, Laya's local answers agreed with the LLM's answers
97.4% of the time. That flow has no labels, so agreement is the only quality
signal.

### What the results show

- **Tuned thresholds trade savings for accuracy, and the trade is visible.**
  Without them, the hybrid flow saves more tokens and loses 10 to 24 points
  of accuracy. With them, code review keeps its accuracy and saves 29.4%.
- **Savings come only from questions the engine answers well.** Laya's
  `tier` and `needs_human` answers never met their thresholds, so routing
  saved nothing. The same is true of the `destructive` and `needs_approval`
  gate questions: only `scope` stayed local.
- **A small local LLM is a strong cheap tier.** The 4B baseline beat Laya on
  every pack. Where the engine cannot answer, route the question to a small
  local model before a frontier model. The measured p50 latency of the 4B
  model was 0.7 to 1.3 s per item, against 0.06 to 0.28 s for Laya.
- **These prompts are minimal.** The baseline prompt holds only the state and
  the typed questions. An agent that asks the same question inside a long
  session sends much more context, so the tokens saved per local answer in a
  real agent session are higher. That was not measured.

### Caveats

- Cost was not measured. Both models ran locally, and no hosted LLM key was
  available. Tokens are measured; cost is tokens multiplied by the prices you
  set.
- Token counts use the Qwen3 tokenizer. A hosted model's tokenizer gives
  different counts for the same text.
- The thresholds were tuned on 20 to 24 `dev` answers per question. The
  `test` flows above were not used to tune them.
- Later runs were faster (for example, 0.29 s against 0.82 s LLM p50 on
  routing), probably from llama.cpp prompt caching. Compare latency only
  within one run.
- The benchmark flows are synthetic. The commit and ROADMAP flows are real
  but have no labels.

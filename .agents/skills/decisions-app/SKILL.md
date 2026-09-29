---
name: decisions-app
description: >
  Use when working with the decisions app: the System One decision engine, its
  providers (laya, clm, jev, fake), DecisionService, the eval harness and
  benchmark, per-question thresholds, the agent packs (route, triage, gate,
  generator), DecisionFixture, or the /api/decisions endpoints. Use when the
  user mentions "decision", "decisions", "laya", "clm", "jev", "typesafe",
  "provider", "System One", "benchmark", "threshold", "dnm decide", or
  "evaluate".
---

# Decisions app

`decisions/` is a provider-agnostic integration with the System One decision
engine. It answers a set of typed questions from a piece of state.

## When to use this skill

- Calling or changing `POST /api/decisions/evaluate` or `/api/decisions/agent/*`
- Adding or changing a provider
- Running the eval harness or tuning per-question thresholds
- Working with the agent packs, MCP tools, or `dnm decide`
- Working with `DecisionFixture` or `seed_decisions`
- Debugging an "install the extra" error

## Providers

| Provider | Backing | Dependency |
|---|---|---|
| `laya` | Open-source, in-process (default) | Base install; downloads its checkpoint on first prediction |
| `clm` | Open-source CLM + Qwen3-8B | `decisions-clm` profile on an NVIDIA GPU host; on Apple Silicon `just clm-encoder-local` + `CLM_ENCODER_URL` (`decisions-clm-host`); or remote `CLM_BASE_URL` |
| `jev` | Hosted TypeSafe API | extra `decisions-jev` + `TYPESAFE_API_KEY` |
| `fake` | Deterministic | none |

Providers never silently fall back. A missing dependency or configuration
fails with a setup hint. A failed CLM HTTP request raises an error.

## Question types

`choice`, `score`, and `noul`. These are Laya's own typed-question names and are
sent to the engine unchanged. **`noul` is not a typo for `null`** — Laya's
README and changelog both use `noul` for yes/no questions, and the engine
rejects other spellings. Do not rename it.

## Endpoint

`POST /api/decisions/evaluate`, registered only when `ENABLE_DECISIONS` is true.

```bash
curl -s http://localhost:8000/api/decisions/evaluate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"state": {"ticket_id": "T-1"},
       "questions": {"refund": {"type": "choice",
                                "instructions": "Approve the refund?",
                                "criteria": {"approve": "within window"}}}}'
```

The server always uses `SYSTEMONE_PROVIDER`. `DecisionRequestSchema` forbids
extra fields, so a request with `provider` gets a 422 response. This stops a
JWT user from selecting `fake` or bypassing the configured engine. Internal
Python callers use `DecisionService(provider="...")`. The MCP tool follows the
same rule.

## Response shape

```json
{
  "answers": {"refund": "approve"},
  "answerConfidence": {"refund": 0.99},
  "confidence": 0.99,
  "provider": "fake",
  "routing": null,
  "fallbackUsed": false,
  "escalationRecommended": false,
  "escalatedQuestions": []
}
```

- `confidence` is the **lowest** per-answer confidence. Laya reports confidence
  per answer and routing metadata; `result_from_raw` normalises both.
  CLM and Jev `noul` answers carry a yes probability. When no separate
  confidence exists, use `max(p, 1-p)` for selected-side confidence.
- Each answer is compared with its question's threshold for the active
  provider in `DECISION_THRESHOLDS_FILE`, or with
  `DECISION_ESCALATION_THRESHOLD`. `escalatedQuestions` lists the weak
  answers. An empty question set is never escalated.
- Confidence is not calibrated. The Laya checkpoint warns: "Treat confidence
  from the affected entries as uncalibrated." Do not present observed scores
  as trusted thresholds. Gate consequential automation until confidence is
  calibrated on representative data.

## Adding a provider

1. Subclass `DecisionProvider` in `decisions/providers/`, set `name`, implement
   `predict` and `is_available`.
2. Return `result_from_raw(response, self.name)` so vendor shapes stay out of
   the API.
3. Register the class in `PROVIDER_REGISTRY` in `decisions/providers/__init__.py`.
4. Add a test that injects a stub client — never the real provider.

See `references/provider-interface.md`.

## Fixtures

`DecisionFixture` stores named example payloads with a native pgvector
`embedding`. `python manage.py seed_decisions` (or `just seed-decisions`) loads
`decisions/data/fixtures/*.json` and is idempotent on `(kind, name)`.

The initial migration creates the Postgres `vector` extension before the table.
SQLite accepts the column type, so tests need no setup.

## Eval harness and benchmark

- `eval_decisions --benchmark --provider <p> --output <file>` runs the five
  domains in `decisions/data/benchmark/` (310 cases, `dev` and `test`
  splits). It accepts JSONL for reviewed traffic. It fails when the provider
  is unavailable; `--skip-unavailable` records a skipped report instead.
- `compare_decisions` compares reports on the `test` split.
- `recommend_thresholds <report> --write <file>` tunes on `dev` and checks on
  `test`.
- Results and caveats: `docs/DECISIONS_BENCHMARK.md`. Laya is the default:
  65.8% against CLM's 62.0% on the test split. Neither routes model tiers
  reliably.

## Agent packs

`AgentDecisionService` answers `route_task`, `triage_change`, `gate_action`,
and `pick_generator`. Each pack reads its questions from a benchmark domain.
Surfaces: `POST /api/decisions/agent/*`, MCP tools, `dnm decide`, and
`just decide`. `escalate` and `ask_human` exit with status 3 on the CLI.
`measure_decision_savings` measures tokens against a baseline LLM. See
`docs/DECISIONS_FOR_AGENTS.md`.

## Testing

Use `FakeProvider` or a scripted `DecisionProvider` stub. Unit tests must not
load a model or touch the network; stub the baseline LLM with
`httpx.MockTransport`.

```bash
uv run pytest decisions/ -v
```

## Common mistakes

- Renaming `noul` to `null`. It breaks the engine contract.
- Adding a silent fallback from laya to jev. Fail loud instead.
- Testing with the real provider. Use `FakeProvider`.
- Expecting a flat `confidence` from the engine. It is per answer; the service
  aggregates with `min`.
- Adding a `provider` field to the API or MCP request. Callers must not choose
  the provider; configure `SYSTEMONE_PROVIDER` instead.
- Sending thresholds from a client. Per-question thresholds come only from
  `DECISION_THRESHOLDS_FILE`.
- Tuning wording or thresholds on the benchmark `test` split. Tune on `dev`.
- Treating `gate_action` `allow` as permission for production or
  irreversible actions. The gate is a first filter; your own policy still
  applies.

---
name: decisions-app
description: >
  Use when working with the decisions app: the System One decision engine, its
  providers (laya, clm, jev, fake), DecisionService, DecisionFixture, or the
  POST /api/decisions/evaluate endpoint. Use when the user mentions "decision",
  "decisions", "laya", "clm", "jev", "typesafe", "provider", "System One",
  "DecisionFixture", or "evaluate".
---

# Decisions app

`decisions/` is a provider-agnostic integration with the System One decision
engine. It answers a set of typed questions from a piece of state.

## When to use this skill

- Calling or changing `POST /api/decisions/evaluate`
- Adding or changing a provider
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
  "escalationRecommended": false
}
```

- `confidence` is the **lowest** per-answer confidence. Laya reports confidence
  per answer and routing metadata; `result_from_raw` normalises both.
  CLM and Jev `noul` answers carry a yes probability. When no separate
  confidence exists, use `max(p, 1-p)` for selected-side confidence.
- `DECISION_ESCALATION_THRESHOLD` decides when a result is flagged. An empty
  question set is never escalated.
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

## Testing

Use `FakeProvider`. Unit tests must not load a model or touch the network.

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

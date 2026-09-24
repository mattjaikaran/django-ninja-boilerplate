# Decisions app

Provider-agnostic integration with the System One decision engine. The app
answers a set of questions from a piece of state, using one of three
providers:

| Provider | Backing | When to use |
|---|---|---|
| `laya` | Laya, in-process (default) | Default engine. Needs the `decisions-laya` extra. |
| `jev` | TypeSafe API | Hosted engine. Needs `decisions-jev` and `TYPESAFE_API_KEY`. |
| `fake` | Deterministic | Tests and local smoke checks. No dependencies. |

Providers never fall back to each other. When a provider cannot run, it
raises `ImproperlyConfigured` with the exact command that fixes it.

## Layout

```
decisions/
├── admin/decision_admin.py            # DecisionFixture admin
├── controllers/decision_controller.py # POST /decisions/evaluate
├── data/fixtures/*.json               # Seed examples
├── management/commands/seed_decisions.py
├── mcp.py                             # Optional MCP tool wrappers
├── models/decision_fixture.py         # Stored example payloads
├── providers/                         # base, fake, laya, jev, registry
├── schemas/decision_schema.py         # Question, request, response, fixture
├── services/decision_service.py       # Provider selection + policy + fixtures
└── tests/
```

## Question types

Question types use Laya's vocabulary and are sent to the engine unchanged:
`choice`, `score`, and `noul` (a yes/no question). `noul` is Laya's own name
for that type, not a typo for `null`.

## Endpoint

`POST /api/decisions/evaluate`

```bash
curl -s http://localhost:8000/api/decisions/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
        "state": {"ticket_id": "T-1", "days_since_purchase": 3},
        "questions": {
          "refund": {
            "type": "choice",
            "instructions": "Approve the refund?",
            "criteria": {"approve": "within window", "deny": "outside window"}
          },
          "churn_risk": {
            "type": "noul",
            "instructions": "Does the customer threaten to cancel?"
          }
        },
        "provider": "fake"
      }'
```

Response:

```json
{
  "answers": {"refund": "approve", "churn_risk": false},
  "answerConfidence": {"refund": 0.99, "churn_risk": 0.99},
  "confidence": 0.99,
  "provider": "fake",
  "routing": null,
  "fallbackUsed": false,
  "escalationRecommended": false
}
```

`confidence` is the **lowest** per-answer confidence: a decision is only as
trustworthy as its weakest answer. Set `DECISION_ESCALATION_THRESHOLD` to
control when a result is flagged for escalation. Laya also reports `routing`
metadata naming the checkpoint that handled the request.

Omit `provider` to use `SYSTEMONE_PROVIDER`. The controller is registered
only when `ENABLE_DECISIONS` is true, so production does not expose it.

## Add a provider

1. Subclass `DecisionProvider` in `decisions/providers/` and set `name`.
2. Implement `predict` and `is_available`.
3. Register the class in `PROVIDER_REGISTRY` in `decisions/providers/__init__.py`.
4. Add a test that injects a stub client and asserts the response mapping.

Return a :class:`DecisionResult`. Use `result_from_raw` to normalise a vendor
response that carries per-answer `confidence`.

## Fixtures

`DecisionFixture` stores named example payloads, with a native pgvector
`embedding` column. `seed_decisions` loads every JSON file in `data/fixtures`
and is idempotent:

```bash
uv run python manage.py seed_decisions
```

Each file declares a `kind` and a `fixtures` list:

```json
{
  "kind": "support_ticket",
  "fixtures": [{"name": "refund", "payload": {"ticket_id": "T-1"}}]
}
```

Postgres needs the `vector` extension. The initial migration creates it on
PostgreSQL before the table, and `docker/postgres/init/01-extensions.sql`
creates it when the Docker volume is first initialised. SQLite accepts the
column type, so `just test` needs no setup.

## Optional extras

```bash
uv sync --extra decisions-laya   # Laya (pulls torch + transformers)
uv sync --extra decisions-jev    # TypeSafe SDK
```

Laya is **opt-in**: it pulls `torch` and `transformers`, so it is never
installed by default. The test suite runs against `FakeProvider` and needs
neither extra. In production, build the provider with `LayaProvider(preload=True)`
to load checkpoints at startup instead of on the first request.

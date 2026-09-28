# Decisions app

Provider-agnostic System One decisions from structured state. Set
`SYSTEMONE_PROVIDER` before starting the app, or select a provider per request:

| Provider | Backing | Setup |
|---|---|---|
| `laya` | Open-source, in-process (default) | Installed with the app; downloads a model checkpoint on first prediction. |
| `clm` | Open-source CLM + Qwen3-8B encoder | Run the `decisions-clm` GPU Compose profile or configure a remote service. |
| `jev` | Hosted TypeSafe API | Install `decisions-jev` and set `TYPESAFE_API_KEY`. |
| `fake` | Deterministic | Tests and local smoke checks only. |

Providers never fall back to each other. Missing configuration fails with an
install or setup hint; an unavailable model service returns an error.

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
  -H "Authorization: Bearer $ACCESS_TOKEN" \
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

## Running the engines

`uv sync --locked` installs Laya. The first prediction downloads its checkpoint
from Hugging Face. On Apple Silicon, Laya runs locally without Qwen3-8B.
The published English checkpoint emitted a temperature-clamping warning during
local inference. Treat its reported confidence as uncalibrated until you
measure it against representative decisions. Never use it as authorization.
Use `LayaProvider(preload=True)` if you need checkpoints loaded before traffic.
Watch model memory when you raise the Gunicorn worker count: each process holds
its own Laya router and loaded weights.
In production, begin with `GUNICORN_WORKERS=1` and
`DJANGO_MEMORY_LIMIT=4G` from `.env.deploy.example` if you enable Laya.
Measure actual resident memory before raising the worker count.

CLM requires a Linux NVIDIA GPU host that can serve Qwen3-8B through vLLM.
With the NVIDIA Container Toolkit installed, set `SYSTEMONE_PROVIDER=clm` in `.env`.
`just dev` then activates the `decisions-clm` profile automatically. Or run:

```bash
docker compose --profile dev --profile decisions-clm up -d --build
# For production, substitute --profile prod for --profile dev.
```

The `clm-encoder` service downloads Qwen3-8B on first start. `clm-api`
downloads the CLM projection head. Both caches use named volumes. The encoder
port stays internal; the CLM API binds host port 8700 on loopback only. Set
`CLM_API_KEY` for access control and `HF_TOKEN` privately if Hugging Face
rate limits anonymous downloads. Compose pins Django's `CLM_BASE_URL` to the
internal service; to connect to an external GPU host, set `CLM_CONTAINER_URL`.
For host-side Django, set `CLM_BASE_URL=http://127.0.0.1:8700`. Without a GPU,
do not start the profile: select Laya instead. CLM never falls back to Laya
when its service is unavailable.

For hosted Jev, install `uv sync --extra decisions-jev` and set
`TYPESAFE_API_KEY` privately. Neither open-source provider needs that key.
In production, explicitly set `ENABLE_DECISIONS=true` to expose this JWT
protected endpoint. A provider's score is not permission to publish, delete,
or spend. Enforce those rules in code and review calibration on your own data.

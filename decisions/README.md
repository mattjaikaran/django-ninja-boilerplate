# Decisions app

Provider-agnostic System One decisions from structured state. Set
`SYSTEMONE_PROVIDER` before you start the app. API and MCP callers cannot
select a provider:

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
├── providers/                         # base, fake, laya, clm, jev, registry
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
        }
      }'
```

Response with `SYSTEMONE_PROVIDER=fake`:

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
strong as its weakest answer. Set `DECISION_ESCALATION_THRESHOLD` to
control when a result is flagged for escalation. Laya also reports `routing`
metadata naming the checkpoint that handled the request.

A `noul` answer from CLM or Jev is the probability of "yes". When the
provider sends no separate confidence, the app uses `max(p, 1 - p)`, so a
confident "no" (`p = 0.03`) has confidence `0.97`.

The server always uses `SYSTEMONE_PROVIDER`. The request schema rejects
unknown fields, so a request that sends `provider` gets a 422 response. This
stops an ordinary JWT user from selecting `fake` or bypassing the configured
engine to reach Jev. Internal Python code can pass a provider name to
`DecisionService(provider=...)`. The controller is registered only when
`ENABLE_DECISIONS` is true, so production does not expose it by default.

## Confidence is not calibrated

Do not use provider confidence to authorize consequential automation, such
as publishing, deleting, refunding, or spending. Keep a human or a rule in
code in the loop until you calibrate confidence on representative data.

- During local inference, the published Laya English checkpoint emitted a
  `RuntimeWarning` that it "ships invalid temperatures" and said: "Treat
  confidence from the affected entries as uncalibrated."
- The scores in this README and in the tests are examples. They are not
  trusted thresholds.
- `DECISION_ESCALATION_THRESHOLD` (default `0.5`) only flags weak results for
  review. It does not make a result above the threshold safe to act on.

To calibrate, record decisions and their reviewed outcomes on your own
traffic. Measure how often answers at each confidence level are correct.
Then choose a threshold for each question, and keep the gate in code.

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
Read [Confidence is not calibrated](#confidence-is-not-calibrated) before you
act on Laya scores.
Use `LayaProvider(preload=True)` if you need checkpoints loaded before traffic.
Watch model memory when you raise the Gunicorn worker count: each process holds
its own Laya router and loaded weights.
In development, the `django` container limit is `DJANGO_DEV_MEMORY_LIMIT`
(default `4G`). On Apple Silicon, the first Laya decision in that container
peaked near 3.1 GiB, and a 1G limit was OOM-killed. In production, begin
with `GUNICORN_WORKERS=1` and `DJANGO_MEMORY_LIMIT=4G` from
`.env.deploy.example` if you enable Laya. Measure actual resident memory
before raising the worker count.

CLM requires a Linux NVIDIA GPU host that can serve Qwen3-8B through vLLM.
With the NVIDIA Container Toolkit installed, set `SYSTEMONE_PROVIDER=clm` in
`.env`. `just dev` then activates the `decisions-clm` profile. It runs
`docker compose up --build`, so it builds `clm-api` on a fresh checkout and
rebuilds it after `deploy/docker/Dockerfile.clm` changes. Or run Compose
directly:

```bash
docker compose --profile dev --profile celery --profile decisions-clm up -d --build
# For production, substitute --profile prod for --profile dev --profile celery.
```

The `clm-encoder` service downloads Qwen3-8B on first start. `clm-api`
downloads the CLM projection head. Both caches use named volumes. The encoder
port stays internal; the CLM API binds host port 8700 on loopback only.

Set `CLM_API_KEY` for access control. Compose passes the same value to
`clm-api` and to every Django service that can call CLM: `django`, `mcp`,
`django-prod`, and `app`. Set `HF_TOKEN` privately if Hugging Face rate
limits anonymous downloads. Compose pins Django's `CLM_BASE_URL` to the
internal service; to connect to an external GPU host, set `CLM_CONTAINER_URL`.
For host-side Django, set `CLM_BASE_URL=http://127.0.0.1:8700`. Without a GPU,
do not start the profile: select Laya instead. CLM never falls back to Laya
when its service is unavailable.

For hosted Jev, install `uv sync --extra decisions-jev` and set
`TYPESAFE_API_KEY` privately. Neither open-source provider needs that key.
In production, explicitly set `ENABLE_DECISIONS=true` to expose this JWT
protected endpoint.

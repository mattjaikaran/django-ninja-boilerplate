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
├── mcp.py                             # evaluate_decision MCP tool + registration
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

- The published Laya English checkpoint emits a `RuntimeWarning` that it
  "ships invalid temperatures" and says: "Treat confidence from the affected
  entries as uncalibrated." Its config clamps one bucket (`choice:11+`, choice
  questions with 11 or more options). The other buckets load, but nobody has
  validated them on your data.
- `choice` and `score` confidence is the top probability minus the mean of
  the others, not a probability. `noul` confidence is `max(p, 1 - p)`.
- The scores in this README and in the tests are examples. They are not
  trusted thresholds.
- `DECISION_ESCALATION_THRESHOLD` (default `0.5`) only flags weak results for
  review. It does not make a result above the threshold safe to act on.

### Measure it: `eval_decisions`

`manage.py eval_decisions` (or `just eval-decisions`) runs a labelled dataset
through a provider and reports accuracy, mean confidence, expected calibration
error (ECE), and, for each threshold from 0.5 to 0.95, the share of answers at
or above it and their accuracy. Use that table to choose a threshold per
question. The bundled `data/eval/support_tickets.json` has 40 hand-labelled
tickets and three questions; replace it with reviewed decisions from your own
traffic.

```bash
just eval-decisions --provider laya
just eval-decisions --provider clm path/to/reviewed.json --json
```

One run on the bundled set (Apple Silicon, CLM encoder from llama.cpp Q8_0):

| Provider | Question | Accuracy | Mean confidence | ECE |
|---|---|---|---|---|
| `laya` | team (3-way choice) | 95.0% | 53.0% | 0.420 |
| `laya` | angry (noul) | 90.0% | 70.9% | 0.191 |
| `laya` | wants_refund (noul) | 97.5% | 81.1% | 0.164 |
| `clm` | team (3-way choice) | 77.5% | 55.5% | 0.220 |
| `clm` | angry (noul) | 72.5% | 78.9% | 0.194 |
| `clm` | wants_refund (noul) | 92.5% | 89.8% | 0.072 |

Read it this way: these are illustrative results on a small synthetic set,
written and labelled by one person. They do not calibrate anything, and they
are not a basis for `DECISION_ESCALATION_THRESHOLD`. On this set, Laya is
underconfident: with the default threshold of 0.5, it would escalate 40% of
`team` answers, and 14 of those 16 were correct. CLM is weaker here, and
more than a quarter of its `angry` answers above 0.8 confidence were wrong.
Both providers were scored on the same sentence-style criteria. Those
criteria were rewritten after seeing CLM's first results on these same 40
tickets, so the CLM numbers are optimistic. Run `eval_decisions` on reviewed
decisions from your own traffic before you pick a threshold.

### Write CLM criteria as answers

CLM scores each option's text as a candidate answer, so phrase criteria as
complete answer sentences. On the bundled set, keyword lists such as
`"Charges, refunds, invoices"` gave 35% on `team`. Sentences such as
`"The billing team, because the ticket is about a charge, payment, invoice,
refund or subscription."` gave 77.5%. For `noul`, pass `criteria` with
`true` and `false` sentences. `"The customer is angry."` versus
`"The customer is not angry."` scored 25% on tone; a descriptive pair scored
72.5%.

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
and is idempotent. A re-seed keeps a fixture's vector while its description
and payload are unchanged, and clears it when they change:

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
PostgreSQL before the table, and `docker/postgres/init/01-init.sql`
creates it when the Docker volume is first initialised. SQLite accepts the
column type, so `just test` needs no setup.

### Similarity search with Qwen3-Embedding-0.6B

`POST /api/decisions/similar` returns the stored fixtures nearest to a new
case, by cosine distance (0 is identical). Use it to show reviewers similar
past cases or to pick examples for a prompt. The embedding model is
Qwen3-Embedding-0.6B (1024 dimensions), served by llama.cpp:

```bash
just up-embeddings      # `embedder` service on the `embeddings` profile (CPU)
just seed-decisions
just embed-decisions    # fills missing vectors; --force recomputes all
curl -s http://localhost:8000/api/decisions/similar \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"text": "Customer wants a refund two months after buying", "kind": "support_ticket", "limit": 3}'
```

On the bundled fixtures, that query returned `refund_outside_window` (0.175)
and `refund_within_window` (0.207) ahead of `enterprise_outage` (0.571).
Similarity finds the topic. It does not apply rules such as the 30-day
window, so keep those in code.

Django reads `DECISION_EMBEDDING_URL` (any OpenAI-compatible
`/v1/embeddings` endpoint), `DECISION_EMBEDDING_MODEL`, and optional
`DECISION_EMBEDDING_API_KEY`. On the host, `just embedder-local` serves the
same model with Metal on port 8091. Queries carry the Qwen3 retrieval
instruction (`DECISION_EMBEDDING_INSTRUCTION`); stored documents do not. A
model with another output width fails loud; change `EMBEDDING_DIMENSIONS`
with a migration to use one.

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

CLM needs a Qwen3-8B encoder. The `decisions-clm` profile serves it with vLLM
on a Linux NVIDIA GPU host. With the NVIDIA Container Toolkit installed, set
`SYSTEMONE_PROVIDER=clm` in `.env`. `just dev` then activates the
`decisions-clm` profile. It runs `docker compose up --build`, so it builds
`clm-api` on a fresh checkout and rebuilds it after
`deploy/docker/Dockerfile.clm` changes. Or run Compose directly:

```bash
docker compose --profile dev --profile celery --profile decisions-clm up -d --build
# For production, substitute --profile prod for --profile dev --profile celery.
```

**Without an NVIDIA GPU (Apple Silicon):** serve the encoder on the host with
llama.cpp and Metal, and run only `clm-api` in Compose:

```bash
brew install llama.cpp
just clm-encoder-local   # Qwen3-8B Q8_0 (8.7 GB download), 127.0.0.1:8090
# in .env:
#   SYSTEMONE_PROVIDER=clm
#   CLM_ENCODER_URL=http://host.docker.internal:8090/v1/embeddings
just dev                 # selects the decisions-clm-host profile
```

On an M2 Pro with 32 GB, a three-question decision took 0.4 to 1.7 s. Running
the 8B encoder (about 9 GB resident) next to the dev stack and Laya is tight
on 32 GB; stop it when you are not using CLM.

Encoder parity: the projection head was trained on vLLM bf16 embeddings. A
check at the same architecture's small size, Qwen3-0.6B Q8_0 in llama.cpp
against `transformers` bf16 last-token hidden states, gave cosine similarity
0.998 to 0.9997 on 15 of 16 CLM input texts, and 0.942 on a one-token input.
So the llama.cpp pipeline (tokenization, final norm, last-token pooling)
matches. The Q8_0 quantization gap at 8B was not measured. `clm-api` is a
small native CPU image (`python:3.12-slim`, about 900 MB) on both Apple
Silicon and GPU hosts; only the encoder needs a GPU or Metal.

The `clm-encoder` service downloads Qwen3-8B on first start. `clm-api`
downloads the CLM projection head. Both caches use named volumes. The encoder
port stays internal; the CLM API binds host port 8700 on loopback only.

Set `CLM_API_KEY` for access control. Compose passes the same value and the
CLM address to `clm-api` and to every Django service that can call CLM:
`django`, `mcp`, every task worker, `django-prod`, the production Celery
services, and `app`. Set `HF_TOKEN` privately if Hugging Face rate
limits anonymous downloads. Compose pins Django's `CLM_BASE_URL` to the
internal service; to connect to an external GPU host, set `CLM_CONTAINER_URL`.
For host-side Django, set `CLM_BASE_URL=http://127.0.0.1:8700`. Without a GPU,
do not start the profile: select Laya instead. CLM never falls back to Laya
when its service is unavailable. An unreachable service or a rejected
`CLM_API_KEY` returns a 500 `provider_unavailable` response that names the
address or the setting to fix.

## MCP tool

`just up-mcp` starts the django-ai-boost SSE server on
`http://127.0.0.1:8001/sse` (loopback only). The `mcp` service sets
`ENABLE_DECISION_MCP=true`, so `DecisionsConfig.ready()` adds
`evaluate_decision(state, questions)` to the server's tool list. The tool uses
the configured provider; a call that passes `provider` fails validation.

For hosted Jev, install `uv sync --extra decisions-jev` and set
`TYPESAFE_API_KEY` privately. Neither open-source provider needs that key.
In production, explicitly set `ENABLE_DECISIONS=true` to expose this JWT
protected endpoint.

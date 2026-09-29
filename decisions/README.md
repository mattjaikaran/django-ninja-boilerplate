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
├── admin/decision_admin.py                  # DecisionFixture admin
├── controllers/decision_controller.py       # POST /decisions/evaluate, /similar
├── controllers/agent_decision_controller.py # POST /decisions/agent/*
├── data/benchmark/<domain>/                 # questions.json + cases.jsonl
├── data/eval/support_tickets.json           # Older 40-ticket eval set
├── data/fixtures/*.json                     # Seed examples
├── data/thresholds.example.json             # Example per-question thresholds
├── management/commands/                     # seed, embed, eval, compare,
│                                            # recommend_thresholds, agent_decide,
│                                            # measure_decision_savings
├── mcp.py                                   # MCP tools + registration
├── models/decision_fixture.py               # Stored example payloads
├── providers/                               # base, fake, laya, clm, jev, registry
├── schemas/                                 # decision and agent decision schemas
├── services/decision_service.py             # Provider selection + escalation
├── services/thresholds.py                   # DECISION_THRESHOLDS_FILE
├── services/agent_service.py                # Agent packs and next steps
├── services/eval_*.py                       # Eval dataset, metrics, runner, compare
├── services/savings_service.py              # Token savings against a baseline LLM
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
  "escalationRecommended": false,
  "escalatedQuestions": []
}
```

`confidence` is the **lowest** per-answer confidence: a decision is only as
strong as its weakest answer. Each answer is compared with its question's
threshold (see [Per-question thresholds](#per-question-thresholds)) or with
`DECISION_ESCALATION_THRESHOLD`. `escalatedQuestions` lists the answers below
their threshold, and `escalationRecommended` is true when that list is not
empty. Laya also reports `routing` metadata naming the checkpoint that
handled the request.

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
- `DECISION_ESCALATION_THRESHOLD` (default `0.5`) and per-question
  thresholds only flag weak answers for review. They do not make an answer
  above the threshold safe to act on.

### Measure it: the eval harness

`eval_decisions` runs labelled cases through one provider and reports
accuracy, mean confidence, expected calibration error (ECE), reliability
bins, coverage and accuracy at each threshold from 0.5 to 0.95, latency (cold,
warm p50 and p95), and cost when `DECISION_PROVIDER_COSTS` sets a price.
`--output` saves a JSON report with every scored answer. It accepts the
original JSON format, JSONL (one reviewed case per line, for your own
traffic), and benchmark domain directories.

```bash
just decisions-benchmark laya          # all 5 domains -> reports/decisions/laya.json
just decisions-benchmark jev --skip-unavailable   # skips only if unavailable up front
just decisions-compare                 # held-out test split, every saved report
just decisions-thresholds reports/decisions/laya.json --target 0.9
just eval-decisions reviewed.jsonl --questions questions.json --provider laya
```

The bundled benchmark (`data/benchmark/`) has 310 labelled cases in five
domains, split into `dev` (109) and `test` (201). On its test split, Laya
scored 65.8% and CLM 62.0% overall; neither was fit for model-tier routing or
for deciding alone that an action is safe. Read
[the benchmark report](../docs/DECISIONS_BENCHMARK.md) for the full results,
the sample sizes, and the caveats. The older 40-ticket set is still in
`data/eval/support_tickets.json` and is the default dataset.

### Per-question thresholds

`recommend_thresholds` tunes a threshold per question on the report's `dev`
split, raises it to `DECISION_ESCALATION_THRESHOLD` (unless you pass
`--allow-below-default`), and checks it on `test`. It writes a tuned value
only when the value held on `test`: at least `--min-support` test answers met
it, at the target accuracy. Every other question gets 1.0, and the table
shows why (`insufficient dev data`, `no threshold met the target on dev`, or
`missed the target on test`). `--write` stores the result in a JSON file
keyed by provider, then by question:

```json
{"laya": {"team": 0.5, "tier": 1.0}, "clm": {"security_sensitive": 0.5}}
```

Set `DECISION_THRESHOLDS_FILE` to that file. `DecisionService` then compares
each answer with its question's threshold for the active provider, and uses
`DECISION_ESCALATION_THRESHOLD` for questions the file does not list. The
response names the weak answers in `escalatedQuestions`. A threshold of 1.0
escalates every answer below certainty. An unreadable or invalid file fails
loud with `ImproperlyConfigured`. Clients cannot send thresholds: the request
schemas reject extra fields with a 422 response.
`data/thresholds.example.json` was tuned on the synthetic benchmark at a 90%
target; only seven rows held on test. Re-tune it on your own reviewed
traffic.

### Write CLM criteria as answers

CLM scores each option's text as a candidate answer, so phrase criteria as
complete answer sentences. On the 40-ticket set, keyword lists such as
`"Charges, refunds, invoices"` gave 35% on `team`. Sentences such as
`"The billing team, because the ticket is about a charge, payment, invoice,
refund or subscription."` gave 77.5%. For `noul`, pass `criteria` with
`true` and `false` sentences. `"The customer is angry."` versus
`"The customer is not angry."` scored 25% on tone; a descriptive pair scored
72.5%. Wording still matters with sentences: on the benchmark, CLM answered
`account` for 63 of 65 `team` cases.

## Agent decisions

`AgentDecisionService` answers four fixed question packs for coding agents
and developer tooling. Each pack reads its questions from the benchmark
domain that measures it, so tuned thresholds apply to the same questions.

| Pack | Benchmark domain | `next_step` values |
|---|---|---|
| `route_task` | `task_routing` | `use_local`, `use_mid`, `use_frontier`, `ask_human`, `escalate` |
| `triage_change` | `code_review_triage` | `deep_review`, `standard_review`, `escalate` |
| `gate_action` | `risk_flags` | `allow`, `ask_human` (fails closed; any non-`local` environment or missing calibration asks a human) |
| `pick_generator` | `generator_choice` | `generate` (with the command), `escalate` |

Surfaces: `POST /api/decisions/agent/{route-task,triage-change,gate-action,pick-generator}`
(JWT), the MCP tools `route_agent_task`, `triage_change`, `gate_agent_action`,
and `pick_generator`, `dnm decide ...`, and `just decide ...`. The CLI exits
with status 3 when the step is `escalate` or `ask_human`.
`measure_decision_savings` measures the LLM tokens a flow saves. Read
[Decisions for agents](../docs/DECISIONS_FOR_AGENTS.md) before you rely on a
pack: on the benchmark, `route_task` and the `destructive` and
`needs_approval` gate questions were not better than guessing the most common
label, and with the shipped thresholds only the gate pack saved tokens.

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
matches, and it probably does not explain most of CLM's accuracy gap to
Laya. The Q8_0 quantization gap at 8B and parity with vLLM were not
measured; a vLLM run on a GPU would settle it. `clm-api` is a small CPU image
(`python:3.12-slim`, 915 MB); only the encoder needs a GPU or Metal. The
image is built and verified on arm64 (Apple Silicon); the amd64 build is not
verified.

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

## MCP tools

`just up-mcp` starts the django-ai-boost SSE server on
`http://127.0.0.1:8001/sse` (loopback only). The `mcp` service sets
`ENABLE_DECISION_MCP=true`, so `DecisionsConfig.ready()` adds five tools to
the server's tool list: `evaluate_decision(state, questions)` and the four
agent tools in [Agent decisions](#agent-decisions). The tools use the
configured provider and thresholds; a call that passes `provider` fails
validation.

For hosted Jev, install `uv sync --extra decisions-jev` and set
`TYPESAFE_API_KEY` privately. Neither open-source provider needs that key.
In production, explicitly set `ENABLE_DECISIONS=true` to expose this JWT
protected endpoint.

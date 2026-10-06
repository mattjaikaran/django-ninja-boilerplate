# AI and data layer

Everything here is opt-in. A default install and the default Compose profiles
do not change. Install the extras you need:

```bash
uv sync --extra dev --extra ai       # pgvector, MCP server
uv sync --extra dev --extra sentry   # Sentry or GlitchTip
```

The Docker images do not install these extras by default. To bake them into
an image, set `UV_EXTRAS` (space-separated) in the shell or `.env` before you
build, for example `UV_EXTRAS="sentry ai" just prod-build`. Compose and the
justfile pass it to both Dockerfiles as a build arg.

| Part | Code | Switch |
|---|---|---|
| pgvector models and migration | `core/ai/models/document.py`, `core/ai/migrations/0001_initial.py` | `AI_ENABLED=true` |
| LLM and embedding client | `core/ai/services/ai_client.py` | `AI_BASE_URL` and models |
| Embedding task | `core/ai/tasks.py` (`embed_document`) | any `TASK_BACKEND` |
| Hybrid search | `core/ai/services/search_service.py` | uses the pgvector models |
| Graph walks | `core/ai/services/graph_service.py` | none (Postgres) |
| App MCP server | `core/mcp/server.py`, mounted in `api/asgi.py` | `MCP_ENABLED=true` |
| Dev MCP server (django-ai-boost) | `scripts/run_dev_mcp.py`, `mcp` Compose service | `just up-mcp` and `DJANGO_MCP_AUTH_TOKEN` |
| Error reporting | `core/observability/sentry.py` | `SENTRY_DSN` |

## Postgres with pgvector

The default Compose image is `postgres:17-alpine`, which has no pgvector. Set
`POSTGRES_IMAGE=pgvector/pgvector:pg17` in `.env` to swap the image of `db`,
`db-prod` and `db-single`. Then set `AI_ENABLED=true` and run
`python manage.py migrate`.

Migration `ai.0001_initial` runs `CREATE EXTENSION IF NOT EXISTS vector`.
`vector` is not a trusted extension, so the database role needs superuser, or
a superuser creates the extension first. The `postgres` role in Compose is a
superuser.

`Document.embedding` is a `VectorField(dimensions=1536)` with an HNSW index
(`vector_cosine_ops`, `m=16`, `ef_construction=64`). `Document.search_vector`
is a stored generated `tsvector` with a GIN index. To use another embedding
size, change `EMBEDDING_DIMENSIONS` and add a migration.

An HNSW index scan returns at most `hnsw.ef_search` rows (default 40). Keep
the vector candidate count at or below it, or raise `hnsw.ef_search` for the
session.

### Document ownership

Each `Document` has a required `owner` foreign key to the user model
(`related_name="ai_documents"`, cascade delete, indexed). Set `owner` when you
create a document. `hybrid_search` and `reachable` take a required `user`
argument and return only that user's rows. If `user` is `None` or anonymous,
they return an empty list. Do not add a read path that skips this filter.
The Django admin can stay global for staff.

## LLM and embedding client

`AIClient` speaks the OpenAI-compatible HTTP API (`/chat/completions`,
`/embeddings`) over httpx. OpenAI, Ollama, vLLM, LM Studio, OpenRouter and a
LiteLLM proxy serve this API.

LiteLLM as a library was not chosen. It adds a large dependency tree for
provider translation that the OpenAI-compatible API already covers, and
`litellm` 1.82.7 and 1.82.8 were malicious releases on PyPI in March 2026
([GHSA-5mg7-485q-xm76](https://docs.litellm.ai/blog/security-update-march-2026)).
To reach a provider without an OpenAI-compatible API, run the LiteLLM proxy as
a separate container and point `AI_BASE_URL` at it.

```python
from core.ai.services import AIClient

with AIClient.from_settings() as client:
    answer = client.chat([{"role": "user", "content": "Hello"}], temperature=0)
    vectors = client.embed(["first text", "second text"])
```

| Setting | Default | Effect |
|---|---|---|
| `AI_BASE_URL` | empty | API root, for example `http://localhost:11434/v1`. Empty raises `ImproperlyConfigured`. |
| `AI_API_KEY` | empty | Sent as `Authorization: Bearer`. Environment only. |
| `AI_PROVIDER_NAME` | `openai` | `gen_ai.provider.name` on traces. |
| `AI_CHAT_MODEL`, `AI_EMBEDDING_MODEL` | empty | Default models. |
| `AI_TIMEOUT` | `60` | Seconds per request. |
| `AI_CACHE_TTL` | `3600` | Seconds a chat response stays cached. `0` turns the cache off. |

Response cache: `chat()` stores each response in the default cache (Valkey)
under `ai:chat:v1:<sha256>`. The hash covers the model, the messages and the
sampling parameters. A cache hit sends no request. Pass `use_cache=False` when
you need a fresh answer at a non-zero temperature.

Tracing: each request opens a CLIENT span named `"{operation} {model}"` with
the OpenTelemetry GenAI attributes `gen_ai.operation.name` (`chat` or
`embeddings`), `gen_ai.provider.name`, `gen_ai.request.model`,
`gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
`gen_ai.response.id`, `gen_ai.response.model`,
`gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`, `server.address`, `server.port`, and
`error.type` on failure. Spans export when `OTEL_ENABLED=true`.

## Hybrid search

`hybrid_search(queryset, user=..., text=..., embedding=...)` ranks the
caller's rows twice: by Postgres full-text rank (`websearch_to_tsquery`) and
by cosine distance. It fuses the two lists with reciprocal rank fusion:
`score = sum(1 / (60 + rank))`. A row that both searches find ranks above a
row that only one finds at the same rank. The function filters the queryset
by `owner_field` (default `owner`) before it ranks rows.

## Graph

Default: `reachable(edge_model, start, user=..., max_depth=3)` walks an edge
table with a Postgres recursive CTE. It returns each reachable node with its
shortest depth and skips cycles. It needs no extension or service.
`DocumentLink` is the example edge model. The walk starts only if `user` owns
`start`, and it visits only nodes that `user` owns.

Apache AGE was not chosen as the default: it needs the `apache/age` Postgres
image (for example `release_PG17_1.7.0`), which does not ship pgvector, so the
AI layer would need a custom image. For Cypher queries or
graph algorithms, start Neo4j 5.26 LTS with the `graph` profile:

```bash
docker compose --profile graph up -d neo4j   # http://localhost:7474, bolt 7687
```

## Qdrant

pgvector is the default vector store. When you outgrow it, start Qdrant with
the `ai` profile and add `qdrant-client` to the `ai` extra:

```bash
docker compose --profile ai up -d qdrant     # http://localhost:6333/dashboard
```

## App MCP server

This is not the `mcp` Compose profile. That profile runs django-ai-boost for
coding agents in development (see
[Development MCP server](#development-mcp-server)). This server lets your
users' MCP clients read selected API routes.

- Path: `/api/mcp` (Streamable HTTP, stateless, JSON responses). nginx already
  proxies `/api/`.
- Runs only under ASGI (`gunicorn api.asgi:application`, or
  `uv run uvicorn api.asgi:application` in development). `runserver` does not
  serve it.
- Auth: send `Authorization: Bearer <access token>` from
  `POST /api/token/pair`. A missing or invalid token gets `401` before any
  tool runs.
- Tools: one per operationId in `MCP_TOOLS` (default
  `auth_get_current_user`, `todo_list_todos`, `todo_search_todos`,
  `todo_get_todo`). Startup fails if an id is unknown or is not a GET route.
- A tool call replays the GET through the full Django stack with the caller's
  token, so Ninja auth, user scoping, throttling and the audit log apply.

Client configuration example:

```json
{
  "mcpServers": {
    "boilerplate": {
      "url": "http://localhost:8000/api/mcp",
      "headers": {"Authorization": "Bearer <access token>"}
    }
  }
}
```

The `mcp` SDK is pinned below 2.0 because django-ai-boost in the `dev` extra
needs fastmcp 3, which needs `mcp<2`.

## Development MCP server

The `mcp` Compose profile runs django-ai-boost, so that a coding agent on your
machine can inspect the project. Use it only in local development. Never
enable it in staging or production.

### What it exposes

django-ai-boost has 12 read-only tools. With them, a caller can:

- Read any setting with `get_setting`, including `SECRET_KEY` and database
  passwords. django-ai-boost does not redact values.
- Read rows from any model with `query_model`, and read the database schema.
- List models, URLs, migrations, and management commands, reverse URLs, run
  system checks, and read recent log lines.

Treat access to this server as access to your development database and
secrets.

### How the profile limits access

- **Bearer token.** django-ai-boost supports one static token. The server
  does not start unless `.env` sets `DJANGO_MCP_AUTH_TOKEN` to 32 or more
  characters. A request to `/sse` or `/messages/` without that token gets
  `401`.
- **Startup guard.** `scripts/run_dev_mcp.py` starts the server. It exits
  with status 2 unless `DJANGO_SETTINGS_MODULE` is `api.settings.dev` and
  `DEBUG` is true. `just up-mcp`, `just up-full`, and `just mcp` also stop
  before Compose starts when the token is missing.
- **Loopback only.** Compose publishes `127.0.0.1:8001`. This address is
  hard-coded and does not follow `DEV_BIND_ADDRESS`. Inside the container,
  the server listens on `0.0.0.0` so that the published port can reach it.
- **Host check.** The server rejects a `Host` header other than `localhost`
  or `127.0.0.1` with `400`. This stops DNS rebinding attacks from a web page
  in your browser.
- **Own network.** The `mcp` service joins only `mcp-network`, which it
  shares with `db` and `valkey`. Other containers cannot connect to it.

### Start the SSE server

```bash
echo "DJANGO_MCP_AUTH_TOKEN=$(openssl rand -hex 32)" >> .env
just up-mcp        # dev stack plus MCP; `just mcp` starts only this service
just mcp-logs      # a guard refusal shows here as "refusing to start"
```

Client configuration example:

```json
{
  "mcpServers": {
    "django-dev": {
      "url": "http://127.0.0.1:8001/sse",
      "headers": {"Authorization": "Bearer <DJANGO_MCP_AUTH_TOKEN>"}
    }
  }
}
```

Remaining risk: the token is static, travels over plain HTTP on loopback,
and is stored in `.env`. Any process on your machine that can read `.env`
can call the tools.

### Prefer stdio

When your agent runs on the host, use the stdio transport instead. It opens
no network port, so it needs no token. The agent starts the process and
talks to it over standard input and output:

```json
{
  "mcpServers": {
    "django-dev": {
      "command": "uv",
      "args": ["run", "django-ai-boost", "--settings", "api.settings.dev"]
    }
  }
}
```

The process reads `.env` from the project root, so start the dev database
first (`just dev`).

## Sentry or GlitchTip

Set `SENTRY_DSN` (GlitchTip uses the same SDK and DSN format) and install the
`sentry` extra. If the DSN is set but `sentry-sdk` is missing, startup fails
with `ImproperlyConfigured`, except with `ENVIRONMENT=development`, which logs
an error and runs without error reporting. `CoreConfig.ready()` starts
the SDK with:

- `send_default_pii=False`: no user email, IP or cookies from the integrations.
- `include_local_variables=False`: no stack-frame locals.
- An event scrubber that filters the SDK's default keys plus this project's
  secret names (`access_token`, `refresh_token`, `csrftoken`, `x-api-key`,
  `email`, `code`, and more) at any depth.

`SENTRY_TRACES_SAMPLE_RATE` (default `0.0`) turns on performance traces.
